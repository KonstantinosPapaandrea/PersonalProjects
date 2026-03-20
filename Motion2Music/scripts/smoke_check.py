#!/usr/bin/env python
from __future__ import annotations

import argparse
import compileall
import os
import subprocess
import sys
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def run_help(root: Path, script_rel: str) -> tuple[bool, str]:
    script = (root / script_rel).resolve()
    if not script.exists():
        return False, f"missing script: {script_rel}"

    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    proc = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=str(root),
        env=env,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout).strip()
        return False, f"{script_rel} --help failed: {tail}"
    return True, f"{script_rel} --help"


def check_imports(root: Path) -> tuple[bool, str]:
    src = str((root / "src").resolve())
    sys.path.insert(0, src)
    try:
        import motion2music  # noqa: F401
        import motion2music.beats  # noqa: F401
        import motion2music.io  # noqa: F401
        import motion2music.ml  # noqa: F401
    except Exception as exc:
        return False, f"import failed: {exc}"
    finally:
        if sys.path and sys.path[0] == src:
            sys.path.pop(0)
    return True, "package imports"


def check_compile(root: Path) -> tuple[bool, str]:
    ok_src = compileall.compile_dir(str(root / "src"), quiet=1)
    ok_scripts = compileall.compile_dir(str(root / "scripts"), quiet=1)
    if ok_src and ok_scripts:
        return True, "compileall src/ scripts/"
    return False, "compileall reported failures"


def main() -> int:
    ap = argparse.ArgumentParser(description="Run a quick health check for Motion2Music.")
    ap.add_argument(
        "--include-musicgen",
        action="store_true",
        help="Also run --help on scripts/generate_music.py (requires optional deps).",
    )
    ap.add_argument(
        "--scripts",
        nargs="*",
        default=None,
        help="Optional script paths to validate with --help (relative to project root).",
    )
    args = ap.parse_args()

    root = project_root()
    print(f"[smoke] root={root}")

    failures = 0

    checks = [check_compile, check_imports]
    for check in checks:
        ok, msg = check(root)
        print(f"[{'OK' if ok else 'FAIL'}] {msg}")
        if not ok:
            failures += 1

    scripts = args.scripts
    if scripts is None:
        scripts = [
            "scripts/beat_refiner_apply.py",
            "scripts/infer_prompt.py",
            "scripts/predict_prompt_and_generate.py",
        ]
        if args.include_musicgen:
            scripts.append("scripts/generate_music.py")

    for script in scripts:
        ok, msg = run_help(root, script)
        print(f"[{'OK' if ok else 'FAIL'}] {msg}")
        if not ok:
            failures += 1

    if failures:
        print(f"[smoke] FAIL ({failures} check(s) failed)")
        return 1

    print("[smoke] PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
