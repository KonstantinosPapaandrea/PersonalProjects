#!/usr/bin/env python3
from __future__ import annotations

import argparse
import cgi
import contextlib
import gc
import importlib
import json
import mimetypes
import os
import sys
import threading
import time
import traceback
import uuid
from dataclasses import dataclass
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import joblib
import numpy as np
import pandas as pd
import torch
from scipy.io import wavfile
from transformers import AutoProcessor, MusicgenForConditionalGeneration


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
SRC_DIR = ROOT / "src"
for candidate in (str(SCRIPTS_DIR), str(SRC_DIR)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from motion2music.io.loadbvh import loadbvh  # noqa: E402
from generate_music import save_wav  # noqa: E402
from infer_prototype_prompt import build_semantic_prompt, compute_temporal_features  # noqa: E402
from lmaTempoExport_v2 import _simple_lma_from_skeleton, detect_beats_from_foot_contacts  # noqa: E402
from predict_prompt_and_generate import compute_motion_features  # noqa: E402


DEFAULT_MODEL_BUNDLE = ROOT / "outputs" / "m2m_train" / "models" / "motion_prototype_prompt_v2_30s.joblib"
DEFAULT_WEB_OUTPUT = ROOT / "outputs" / "web_pipeline" / "sessions"
MUSICGEN_QUALITY_MODELS = {
    "preview": "facebook/musicgen-small",
    "better": "facebook/musicgen-medium",
    "best": "facebook/musicgen-large",
}


def sanitize_name(name: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in name)
    safe = safe.strip("._")
    return safe or "upload.bvh"


def path_to_url(path: Path) -> str | None:
    try:
        rel = path.resolve().relative_to(ROOT.resolve())
    except ValueError:
        return None
    return "/" + rel.as_posix()


def json_ready(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(v) for v in value]
    if isinstance(value, np.generic):
        return value.item()
    return str(value)


def server_log(message: str) -> None:
    print(f"[motion2music-web] {message}", flush=True)


@contextlib.contextmanager
def prepended_path(path: Path):
    text = str(path)
    inserted = False
    if text not in sys.path:
        sys.path.insert(0, text)
        inserted = True
    try:
        yield
    finally:
        if inserted:
            with contextlib.suppress(ValueError):
                sys.path.remove(text)


def find_lma_repo() -> Path | None:
    env = os.environ.get("M2M_LMA_REPO", "").strip()
    candidates = [
        Path(env) if env else None,
        ROOT / "lma-feature-extraction-main",
        ROOT.parent / "lma-feature-extraction-main",
        Path(r"C:\Users\Vido\Desktop\Motion2Music\Motion2Music_OLD\lma-feature-extraction-main"),
    ]
    for candidate in candidates:
        if candidate and (candidate / "create_annotator.py").exists():
            return candidate.resolve()
    return None


def resolve_musicgen_model(quality: str | None, explicit_model: str | None = None) -> tuple[str, str]:
    if explicit_model:
        return (quality or "custom"), str(explicit_model)
    q = str(quality or "preview").strip().lower()
    if q not in MUSICGEN_QUALITY_MODELS:
        q = "preview"
    return q, MUSICGEN_QUALITY_MODELS[q]


@dataclass
class ExtractionResult:
    lma_df: pd.DataFrame
    beats_df: pd.DataFrame
    fps: float
    duration_s: float
    frame_count: int
    downsample_step: int
    lma_mode: str
    lma_repo: str | None
    error: str | None = None


class MotionPipeline:
    def __init__(self, model_bundle: Path, output_root: Path, lma_repo: Path | None = None):
        self.model_bundle_path = model_bundle.resolve()
        self.output_root = output_root.resolve()
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.lma_repo = lma_repo.resolve() if lma_repo else None
        self.bundle = joblib.load(self.model_bundle_path)
        if str(self.bundle.get("bundle_type", "")) != "motion_prototype_prompt_v2":
            raise RuntimeError("Unsupported model bundle for web pipeline.")
        self._annotator_class = None
        self._bundle_lock = threading.Lock()

    def _load_repo_annotator_class(self):
        if self._annotator_class is not None:
            return self._annotator_class
        if not self.lma_repo:
            return None
        with prepended_path(self.lma_repo):
            module = importlib.import_module("create_annotator")
            self._annotator_class = getattr(module, "LMAAnnotator", None)
        return self._annotator_class

    def extract_lma_and_beats(
        self,
        bvh_path: Path,
        out_dir: Path,
        *,
        window_style_word: int = 16,
        step_style_word: int = 4,
        min_interval_s: float = 0.25,
        dedup_within_s: float = 0.10,
    ) -> ExtractionResult:
        skeleton, frame_times, duration_s, fps = loadbvh(bvh_path)
        fps = float(fps)
        downsample_step = max(1, int(round(fps / 20.0)))
        error = None

        lma_df = None
        lma_mode = "simple"
        if self.lma_repo:
            annotator_class = self._load_repo_annotator_class()
            if annotator_class is not None:
                try:
                    annotator = annotator_class.create(
                        fps=int(round(fps)),
                        downsample_step=downsample_step,
                        window_style_word=window_style_word,
                        step_style_word=step_style_word,
                    )
                    lma_df = annotator.fit_to_joints(skeleton.d_xyz)
                    if "LMA_MODE" not in lma_df.columns:
                        lma_df["LMA_MODE"] = "repo"
                    lma_mode = "repo"
                except Exception as exc:  # pragma: no cover - fallback path
                    error = f"Repo LMA failed, fell back to simple extractor: {exc}"

        if lma_df is None:
            lma_df = _simple_lma_from_skeleton(
                skeleton.d_xyz,
                skeleton.joints,
                fps=fps,
                downsample_step=downsample_step,
                window_style_word=window_style_word,
                step_style_word=step_style_word,
            )

        lma_df["START_FRAME_ORIG"] = lma_df["START_FRAME"] * downsample_step
        lma_df["END_FRAME_ORIG"] = lma_df["END_FRAME"] * downsample_step
        lma_df["START_TIME_S"] = lma_df["START_FRAME_ORIG"] / fps
        lma_df["END_TIME_S"] = lma_df["END_FRAME_ORIG"] / fps

        beat_frames = detect_beats_from_foot_contacts(
            skeleton,
            fps=fps,
            min_interval_s=min_interval_s,
            dedup_within_s=dedup_within_s,
        )
        beat_times = beat_frames / fps
        beats_df = pd.DataFrame(
            {
                "beat_index": np.arange(len(beat_frames), dtype=int),
                "frame": beat_frames.astype(int),
                "time_s": beat_times.astype(float),
                "method": ["heuristic_foot_contacts"] * len(beat_frames),
            }
        )

        stem = bvh_path.stem
        lma_path = out_dir / f"{stem}_lma.csv"
        beats_path = out_dir / f"{stem}_beats.csv"
        lma_df.to_csv(lma_path, index=False)
        beats_df.to_csv(beats_path, index=False)

        return ExtractionResult(
            lma_df=lma_df,
            beats_df=beats_df,
            fps=fps,
            duration_s=float(duration_s),
            frame_count=int(len(frame_times)),
            downsample_step=downsample_step,
            lma_mode=lma_mode,
            lma_repo=str(self.lma_repo) if self.lma_repo else None,
            error=error,
        )

    def analyze_bvh(self, bvh_path: Path, session_dir: Path, *, top_k: int = 3) -> dict[str, Any]:
        extracted = self.extract_lma_and_beats(bvh_path, session_dir)
        lma_df = extracted.lma_df
        beats_df = extracted.beats_df

        feat = compute_motion_features(lma_df, beats_df)
        feat |= compute_temporal_features(lma_df, beats_df, n_win=4)

        x_cols = list(self.bundle["x_cols"])
        x = np.zeros((1, len(x_cols)), dtype=np.float32)
        for j, column in enumerate(x_cols):
            value = feat.get(column, 0.0)
            x[0, j] = float(value) if np.isfinite(value) else 0.0

        clf = self.bundle["classifier"]
        proba = clf.predict_proba(x)[0]
        classes = clf.named_steps["clf"].classes_
        order = np.argsort(-proba)
        top_k = int(max(1, min(int(top_k), len(order))))

        class_to_name = {int(k): str(v) for k, v in self.bundle.get("class_to_name", {}).items()}
        name_to_phrase = {str(k): str(v) for k, v in self.bundle.get("name_to_phrase", {}).items()}
        sem_stats = self.bundle.get("semantic_train_stats", {})
        base_prompt, sem_scores, sem_tags, bpm = build_semantic_prompt(lma_df, beats_df, sem_stats)

        ranked = []
        for rank in range(top_k):
            idx = int(order[rank])
            class_id = int(classes[idx])
            name = class_to_name.get(class_id, f"cluster_{class_id}")
            phrase = name_to_phrase.get(name, name)
            prompt = base_prompt if phrase in base_prompt else f"{base_prompt}, {phrase}"
            ranked.append(
                {
                    "rank": rank + 1,
                    "prototype_id": class_id,
                    "prototype_name": name,
                    "prototype_phrase": phrase,
                    "probability": float(proba[idx]),
                    "prompt": prompt,
                }
            )

        stem = bvh_path.stem
        lma_path = session_dir / f"{stem}_lma.csv"
        beats_path = session_dir / f"{stem}_beats.csv"
        payload = {
            "session_id": session_dir.name,
            "bvh_name": bvh_path.name,
            "bvh_url": path_to_url(bvh_path),
            "model_bundle": str(self.model_bundle_path),
            "lma_csv": str(lma_path),
            "beats_csv": str(beats_path),
            "lma_url": path_to_url(lma_path),
            "beats_url": path_to_url(beats_path),
            "base_prompt": base_prompt,
            "prompt_top1": ranked[0]["prompt"],
            "bpm": float(bpm),
            "semantic_scores": {k: float(v) for k, v in sem_scores.items()},
            "semantic_tags": {k: str(v) for k, v in sem_tags.items()},
            "topk": ranked,
            "extractor": {
                "lma_mode": extracted.lma_mode,
                "lma_repo": extracted.lma_repo,
                "downsample_step": extracted.downsample_step,
                "warning": extracted.error,
            },
            "motion": {
                "fps": extracted.fps,
                "duration_s": extracted.duration_s,
                "frame_count": extracted.frame_count,
                "beat_count": int(len(beats_df)),
            },
            "feature_snapshot": {
                key: float(feat.get(key, 0.0))
                for key in ("beat_count", "beat_rate_hz", "bpm_motion", "ibi_mean_s", "ibi_std_s")
            },
        }
        (session_dir / "analysis.json").write_text(json.dumps(json_ready(payload), indent=2), encoding="utf-8")
        (session_dir / "prompt_top1.txt").write_text(ranked[0]["prompt"] + "\n", encoding="utf-8")
        (session_dir / "prompts_topk.txt").write_text(
            "\n".join(f"{item['rank']}. p={item['probability']:.4f} {item['prototype_name']} -> {item['prompt']}" for item in ranked) + "\n",
            encoding="utf-8",
        )
        payload["analysis_url"] = path_to_url(session_dir / "analysis.json")
        return payload


class MusicGenService:
    def __init__(self, model_id: str = "facebook/musicgen-small", force_cpu: bool = False):
        self.model_id = model_id
        self.force_cpu = force_cpu
        self.device = "cpu" if force_cpu or not torch.cuda.is_available() else "cuda"
        self.dtype = torch.float32 if self.device == "cpu" else torch.float16
        self._processor = None
        self._model = None
        self._lock = threading.Lock()

    @property
    def is_loaded(self) -> bool:
        return self._processor is not None and self._model is not None

    def _ensure_loaded(self) -> None:
        if self._processor is not None and self._model is not None:
            return
        self._processor = AutoProcessor.from_pretrained(self.model_id)
        self._model = MusicgenForConditionalGeneration.from_pretrained(self.model_id, torch_dtype=self.dtype)
        self._model.to(self.device)
        self._model.eval()

    def unload(self) -> None:
        with self._lock:
            self._processor = None
            self._model = None
        gc.collect()
        if torch.cuda.is_available():
            with contextlib.suppress(Exception):
                torch.cuda.empty_cache()

    def generate(
        self,
        prompt: str,
        duration: float,
        out_path: Path,
        seed: int = 1234,
        status_cb=None,
    ) -> dict[str, Any]:
        prompt = prompt.strip()
        if not prompt:
            raise ValueError("Prompt is empty.")
        duration = float(max(1.0, min(duration, 60.0)))

        with self._lock:
            if status_cb:
                if not self.is_loaded:
                    status_cb("loading_model", "Loading MusicGen model weights.")
                else:
                    status_cb("loading_model", "MusicGen model already loaded.")
            self._ensure_loaded()
            torch.manual_seed(seed)
            np.random.seed(seed)
            if status_cb:
                status_cb("preparing_inputs", "Preparing prompt conditioning.")
            inputs = self._processor(text=[prompt], padding=True, return_tensors="pt")
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            max_new_tokens = max(1, int(round(duration * 50)))
            if status_cb:
                if self.device == "cpu":
                    eta_minutes = max(1.0, duration * 0.15)
                    status_cb(
                        "generating_audio",
                        f"Generating audio on CPU. This can take a while for longer clips.",
                        extra={"eta_note": f"Estimated {eta_minutes:.1f} min for {duration:.0f}s audio on CPU."},
                    )
                else:
                    status_cb("generating_audio", "Generating audio.")
            with torch.no_grad():
                audio_values = self._model.generate(**inputs, max_new_tokens=max_new_tokens)
            audio = audio_values.detach().cpu().float()
            if audio.ndim == 3:
                audio = audio[0, 0].numpy()
            elif audio.ndim == 2:
                audio = audio[0].numpy()
            else:
                raise RuntimeError(f"Unexpected generated audio tensor shape: {tuple(audio.shape)}")
            sr = int(self._model.config.audio_encoder.sampling_rate)
            if status_cb:
                status_cb("writing_wav", "Writing generated WAV file.")
            save_wav(out_path, sr, audio)
        return {
            "out_path": str(out_path),
            "sampling_rate": sr,
            "duration_requested": duration,
            "seed": seed,
            "device": self.device,
            "model_id": self.model_id,
        }


class MusicGenManager:
    def __init__(self, default_model_id: str, force_cpu: bool = False):
        self.default_model_id = default_model_id
        self.force_cpu = force_cpu
        self._lock = threading.Lock()
        self._active_model_id: str | None = None
        self._active_service: MusicGenService | None = None

    @property
    def device(self) -> str:
        return "cpu" if self.force_cpu or not torch.cuda.is_available() else "cuda"

    @property
    def active_model_id(self) -> str:
        return self._active_model_id or self.default_model_id

    @property
    def is_loaded(self) -> bool:
        return self._active_service is not None and self._active_service.is_loaded

    def get_service(self, model_id: str | None = None) -> MusicGenService:
        requested = str(model_id or self.default_model_id)
        with self._lock:
            if self._active_service is not None and self._active_model_id == requested:
                return self._active_service

            if self._active_service is not None:
                self._active_service.unload()
                self._active_service = None
                self._active_model_id = None

            service = MusicGenService(model_id=requested, force_cpu=self.force_cpu)
            self._active_service = service
            self._active_model_id = requested
            return service


class Motion2MusicApp:
    def __init__(self, model_bundle: Path, output_root: Path, musicgen_model: str, force_cpu: bool, lma_repo: Path | None):
        self.pipeline = MotionPipeline(model_bundle=model_bundle, output_root=output_root, lma_repo=lma_repo)
        self.musicgen = MusicGenManager(default_model_id=musicgen_model, force_cpu=force_cpu)
        self.output_root = output_root.resolve()
        self.jobs: dict[str, dict[str, Any]] = {}
        self.jobs_lock = threading.Lock()

    def create_session_dir(self) -> Path:
        session_id = time.strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
        session_dir = self.output_root / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        return session_dir

    def _set_job(self, job_id: str, **updates: Any) -> None:
        with self.jobs_lock:
            job = self.jobs.get(job_id)
            if not job:
                return
            job.update(json_ready(updates))
            job["updated_at"] = time.time()

    def _create_job(
        self,
        *,
        kind: str,
        session_id: str | None,
        prompt: str,
        duration: float,
        seed: int,
        quality: str,
        model_id: str,
    ) -> dict[str, Any]:
        job_id = uuid.uuid4().hex
        now = time.time()
        job = {
            "job_id": job_id,
            "kind": kind,
            "session_id": session_id,
            "status": "queued",
            "stage": "queued",
            "message": "Job queued.",
            "progress": 0.0,
            "created_at": now,
            "updated_at": now,
            "prompt": prompt,
            "duration": float(duration),
            "seed": int(seed),
            "quality": quality,
            "model_id": model_id,
            "result": None,
            "error": None,
            "trace": [
                {
                    "ts": now,
                    "stage": "queued",
                    "message": "Job queued.",
                }
            ],
        }
        with self.jobs_lock:
            self.jobs[job_id] = job
        return job

    def _append_job_trace(self, job_id: str, *, stage: str, message: str) -> None:
        with self.jobs_lock:
            job = self.jobs.get(job_id)
            if not job:
                return
            trace = job.setdefault("trace", [])
            trace.append({"ts": time.time(), "stage": stage, "message": message})

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self.jobs_lock:
            job = self.jobs.get(job_id)
            if not job:
                return None
            return json_ready(dict(job))

    def handle_bvh_upload(self, filename: str, file_data: bytes, *, top_k: int = 3) -> dict[str, Any]:
        session_dir = self.create_session_dir()
        clean_name = sanitize_name(filename)
        if not clean_name.lower().endswith(".bvh"):
            clean_name += ".bvh"
        bvh_path = session_dir / clean_name
        bvh_path.write_bytes(file_data)
        analysis = self.pipeline.analyze_bvh(bvh_path, session_dir, top_k=top_k)
        return analysis

    def _run_generation_job(
        self,
        job_id: str,
        session_id: str | None,
        prompt: str,
        duration: float,
        seed: int,
        quality: str,
        model_id: str,
    ) -> None:
        session_dir = self.output_root / session_id if session_id else self.create_session_dir()
        session_dir.mkdir(parents=True, exist_ok=True)
        self._set_job(
            job_id,
            session_id=session_dir.name,
            status="running",
            stage="starting",
            message=f"Starting MusicGen job ({quality}, {Path(model_id).name if '\\' in model_id else model_id}).",
            progress=0.05,
        )
        self._append_job_trace(job_id, stage="starting", message=f"Starting MusicGen job with quality '{quality}' and model '{model_id}'.")

        stamp = time.strftime("%H%M%S")
        out_path = session_dir / f"generated_{stamp}.wav"

        progress_map = {
            "loading_model": 0.15,
            "preparing_inputs": 0.30,
            "generating_audio": 0.65,
            "writing_wav": 0.92,
        }

        def status_cb(stage: str, message: str, extra: dict[str, Any] | None = None):
            updates = {
                "status": "running",
                "stage": stage,
                "message": message,
                "progress": progress_map.get(stage, 0.5),
            }
            if extra:
                updates.update(extra)
            self._set_job(job_id, **updates)
            self._append_job_trace(job_id, stage=stage, message=message)
            server_log(f"job={job_id} stage={stage} {message}")

        try:
            requested_model_id = model_id
            requested_quality = quality
            try:
                service = self.musicgen.get_service(model_id)
                meta = service.generate(
                    prompt=prompt,
                    duration=duration,
                    out_path=out_path,
                    seed=seed,
                    status_cb=status_cb,
                )
            except OSError as exc:
                should_fallback = (
                    model_id == MUSICGEN_QUALITY_MODELS.get("best")
                    and getattr(exc, "errno", None) == 22
                )
                if not should_fallback:
                    raise
                fallback_quality = "better"
                fallback_model_id = MUSICGEN_QUALITY_MODELS[fallback_quality]
                fallback_message = (
                    "Large MusicGen model failed to load on this setup "
                    f"({exc}). Falling back to medium quality."
                )
                server_log(f"job={job_id} {fallback_message}")
                self._set_job(
                    job_id,
                    stage="fallback",
                    message=fallback_message,
                    progress=0.12,
                    requested_model_id=requested_model_id,
                    fallback_model_id=fallback_model_id,
                )
                self._append_job_trace(job_id, stage="fallback", message=fallback_message)
                quality = fallback_quality
                model_id = fallback_model_id
                service = self.musicgen.get_service(model_id)
                meta = service.generate(
                    prompt=prompt,
                    duration=duration,
                    out_path=out_path,
                    seed=seed,
                    status_cb=status_cb,
                )
                meta["requested_model_id"] = requested_model_id
                meta["fallback_model_id"] = fallback_model_id
                meta["requested_quality"] = requested_quality
                meta["effective_quality"] = quality
            result = {
                "session_id": session_dir.name,
                "prompt": prompt,
                "audio_path": str(out_path),
                "audio_url": path_to_url(out_path),
                "audio_name": out_path.name,
            }
            result.update(meta)
            (session_dir / "last_generation.json").write_text(json.dumps(json_ready(result), indent=2), encoding="utf-8")
            self._set_job(
                job_id,
                status="completed",
                stage="completed",
                message="Music generation complete.",
                progress=1.0,
                result=result,
            )
            self._append_job_trace(job_id, stage="completed", message="Music generation complete.")
        except Exception as exc:  # pragma: no cover - runtime protection
            details = traceback.format_exc()
            server_log(f"job={job_id} failed: {exc}\n{details}")
            self._set_job(
                job_id,
                status="failed",
                stage="failed",
                message=str(exc),
                error=str(exc),
                error_trace=details,
                progress=1.0,
            )
            self._append_job_trace(job_id, stage="failed", message=str(exc))

    def start_generation_job(
        self,
        session_id: str | None,
        prompt: str,
        duration: float,
        seed: int,
        quality: str,
        model_id: str,
    ) -> dict[str, Any]:
        job = self._create_job(
            kind="generate_music",
            session_id=session_id,
            prompt=prompt,
            duration=duration,
            seed=seed,
            quality=quality,
            model_id=model_id,
        )
        worker = threading.Thread(
            target=self._run_generation_job,
            args=(job["job_id"], session_id, prompt, duration, seed, quality, model_id),
            daemon=True,
        )
        worker.start()
        return job

    def generate_music(self, session_id: str | None, prompt: str, duration: float, seed: int, model_id: str) -> dict[str, Any]:
        session_dir = self.output_root / session_id if session_id else self.create_session_dir()
        session_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%H%M%S")
        out_path = session_dir / f"generated_{stamp}.wav"
        meta = self.musicgen.get_service(model_id).generate(prompt=prompt, duration=duration, out_path=out_path, seed=seed)
        payload = {
            "session_id": session_dir.name,
            "prompt": prompt,
            "audio_path": str(out_path),
            "audio_url": path_to_url(out_path),
            "audio_name": out_path.name,
        }
        payload.update(meta)
        (session_dir / "last_generation.json").write_text(json.dumps(json_ready(payload), indent=2), encoding="utf-8")
        return payload


class Motion2MusicHandler(SimpleHTTPRequestHandler):
    app: Motion2MusicApp

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, fmt: str, *args) -> None:
        server_log(f"[web] {self.address_string()} - {fmt % args}")

    def _send_json(self, payload: dict[str, Any], status: int = HTTPStatus.OK) -> None:
        data = json.dumps(json_ready(payload), indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _send_error(self, message: str, status: int = HTTPStatus.BAD_REQUEST, *, details: str | None = None) -> None:
        payload = {"ok": False, "error": message}
        if details:
            payload["details"] = details
        self._send_json(payload, status=status)

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length > 0 else b"{}"
        return json.loads(raw.decode("utf-8") or "{}")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", "/cchadj.github.io-main/bvh_music_viewer.html")
            self.end_headers()
            return
        if parsed.path == "/api/health":
            self._send_json(
                {
                    "ok": True,
                    "root": str(ROOT),
                    "model_bundle": str(self.app.pipeline.model_bundle_path),
                    "lma_repo": str(self.app.pipeline.lma_repo) if self.app.pipeline.lma_repo else None,
                    "musicgen_model": self.app.musicgen.active_model_id,
                    "musicgen_device": self.app.musicgen.device,
                    "musicgen_loaded": self.app.musicgen.is_loaded,
                    "musicgen_quality_models": MUSICGEN_QUALITY_MODELS,
                    "torch_version": torch.__version__,
                    "torch_cuda_build": torch.version.cuda,
                    "torch_cuda_available": torch.cuda.is_available(),
                }
            )
            return
        if parsed.path == "/api/job-status":
            params = parse_qs(parsed.query or "")
            job_id = str(params.get("job_id", [""])[0]).strip()
            if not job_id:
                self._send_error("Missing job_id.")
                return
            job = self.app.get_job(job_id)
            if not job:
                self._send_error("Job not found.", status=HTTPStatus.NOT_FOUND)
                return
            job["ok"] = True
            self._send_json(job)
            return
        return super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/analyze-bvh":
                self._handle_analyze_bvh(parsed)
                return
            if parsed.path == "/api/generate-music":
                self._handle_generate_music()
                return
            self._send_error("Unknown API route.", status=HTTPStatus.NOT_FOUND)
        except Exception as exc:  # pragma: no cover - runtime protection
            traceback.print_exc()
            self._send_error("Internal server error.", status=HTTPStatus.INTERNAL_SERVER_ERROR, details=str(exc))

    def _handle_analyze_bvh(self, parsed) -> None:
        server_log("POST /api/analyze-bvh")
        ctype = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in ctype:
            self._send_error("Expected multipart/form-data with a bvh file.")
            return

        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": ctype,
            },
        )
        if "bvh" not in form:
            self._send_error("Missing 'bvh' file field.")
            return

        file_item = form["bvh"]
        filename = getattr(file_item, "filename", "") or "upload.bvh"
        file_data = file_item.file.read()
        if not file_data:
            self._send_error("Uploaded BVH file was empty.")
            return

        params = parse_qs(parsed.query or "")
        top_k = int(params.get("top_k", ["3"])[0])
        server_log(f"Analyzing BVH '{filename}' ({len(file_data)} bytes), top_k={top_k}.")
        payload = self.app.handle_bvh_upload(filename=filename, file_data=file_data, top_k=top_k)
        payload["ok"] = True
        self._send_json(payload)

    def _handle_generate_music(self) -> None:
        payload = self._read_json_body()
        prompt = str(payload.get("prompt", "")).strip()
        if not prompt:
            self._send_error("Missing prompt.")
            return
        session_id = str(payload.get("session_id", "")).strip() or None
        duration = float(payload.get("duration", 30.0))
        seed = int(payload.get("seed", 1234))
        quality, model_id = resolve_musicgen_model(
            str(payload.get("quality", "preview") or "preview"),
            str(payload.get("model_id", "")).strip() or None,
        )
        server_log(
            f"POST /api/generate-music session_id={session_id or '-'} quality={quality} "
            f"model_id={model_id} duration={duration} seed={seed} prompt_len={len(prompt)}"
        )
        result = self.app.start_generation_job(
            session_id=session_id,
            prompt=prompt,
            duration=duration,
            seed=seed,
            quality=quality,
            model_id=model_id,
        )
        result["ok"] = True
        self._send_json(result, status=HTTPStatus.ACCEPTED)


def make_handler(app: Motion2MusicApp):
    class BoundHandler(Motion2MusicHandler):
        pass

    BoundHandler.app = app
    return BoundHandler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve the Motion2Music BVH web player with analyze/generate endpoints.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8124)
    parser.add_argument("--model-bundle", type=Path, default=DEFAULT_MODEL_BUNDLE)
    parser.add_argument("--out-root", type=Path, default=DEFAULT_WEB_OUTPUT)
    parser.add_argument("--musicgen-model", default="facebook/musicgen-small")
    parser.add_argument("--cpu", action="store_true", help="Force MusicGen to CPU.")
    parser.add_argument("--lma-repo", type=Path, default=None, help="Optional path to lma-feature-extraction-main.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    lma_repo = args.lma_repo.resolve() if args.lma_repo else find_lma_repo()
    app = Motion2MusicApp(
        model_bundle=args.model_bundle.resolve(),
        output_root=args.out_root.resolve(),
        musicgen_model=args.musicgen_model,
        force_cpu=bool(args.cpu),
        lma_repo=lma_repo,
    )
    handler = make_handler(app)
    with ThreadingHTTPServer((args.host, args.port), handler) as server:
        print(f"[motion2music-web] root={ROOT}")
        print(f"[motion2music-web] player=http://{args.host}:{args.port}/cchadj.github.io-main/bvh_music_viewer.html")
        print(f"[motion2music-web] model_bundle={app.pipeline.model_bundle_path}")
        print(f"[motion2music-web] lma_repo={app.pipeline.lma_repo}")
        print(f"[motion2music-web] musicgen_default_model={app.musicgen.active_model_id} device={app.musicgen.device}")
        server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
