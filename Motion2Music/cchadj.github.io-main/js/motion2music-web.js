(function () {
  const statusEl = document.getElementById("pipelineStatus");
  const metaEl = document.getElementById("pipelineMeta");
  const analyzeBtn = document.getElementById("pipelineAnalyzeBtn");
  const generateBtn = document.getElementById("pipelineGenerateBtn");
  const qualityEl = document.getElementById("pipelineQuality");
  const durationEl = document.getElementById("pipelineDuration");
  const seedEl = document.getElementById("pipelineSeed");
  const genreEl = document.getElementById("pipelineGenre");
  const instrumentsEl = document.getElementById("pipelineInstruments");
  const promptChoicesEl = document.getElementById("pipelinePromptChoices");
  const promptEl = document.getElementById("pipelinePrompt");
  const semanticsEl = document.getElementById("pipelineSemantics");
  const prototypesEl = document.getElementById("pipelinePrototypes");
  const generateStatusEl = document.getElementById("pipelineGenerateStatus");
  const audioLinkEl = document.getElementById("pipelineAudioLink");
  const toggleBtn = document.getElementById("pipelineToggle");
  const bodyEl = document.getElementById("pipelineBody");
  const traceEl = document.getElementById("pipelineTrace");

  if (!statusEl || !metaEl || !analyzeBtn || !generateBtn || !promptEl || !traceEl || !genreEl || !instrumentsEl || !qualityEl) {
    return;
  }

  const QUALITY_LABELS = {
    preview: "Preview",
    better: "Better",
    best: "Best",
  };

  const GENRE_PRESETS = {
    auto: {
      label: "",
      instruments: "",
    },
    jazz: {
      label: "jazz ensemble",
      instruments: "trumpets, saxophone, upright bass, piano, brushed acoustic drums",
    },
    hiphop: {
      label: "hip-hop track",
      instruments: "boom-bap drums, deep bass, sampled keys, vinyl-style percussion",
    },
    electronic: {
      label: "electronic track",
      instruments: "synth bass, drum machine, bright synth leads, punchy electronic drums",
    },
    cinematic: {
      label: "cinematic score",
      instruments: "strings, brass, low percussion, piano, atmospheric pads",
    },
    ambient: {
      label: "ambient piece",
      instruments: "soft pads, piano, warm synth textures, light percussion",
    },
    orchestral: {
      label: "orchestral score",
      instruments: "strings, brass, woodwinds, timpani, piano",
    },
    rock: {
      label: "rock track",
      instruments: "electric guitar, bass guitar, live drums, rhythmic piano",
    },
    funk: {
      label: "funk groove",
      instruments: "syncopated bass, rhythm guitar, clavinet, brass section, tight drums",
    },
  };

  const SEMANTIC_ORDER = [
    "energy",
    "heaviness",
    "sharpness",
    "control",
    "expansiveness",
    "rhythmic_stability",
    "arousal",
    "valence",
    "dynamic",
  ];

  const state = {
    latestFile: null,
    latestSlot: null,
    latestLoadedMeta: null,
    analysis: null,
    analyzeToken: 0,
    isAnalyzing: false,
    isGenerating: false,
    generationJobId: null,
    traceLines: [],
    health: null,
    jobPollHandle: null,
    basePrompt: "",
  };

  function setStatus(message, tone) {
    const palette = {
      info: { bg: "#132031", fg: "#dcecff" },
      success: { bg: "#173222", fg: "#dff7e7" },
      warn: { bg: "#3a2d14", fg: "#fff0c4" },
      error: { bg: "#3d1820", fg: "#ffd7dd" },
      busy: { bg: "#1a2440", fg: "#e2ebff" },
    };
    const style = palette[tone] || palette.info;
    statusEl.style.background = style.bg;
    statusEl.style.color = style.fg;
    statusEl.textContent = message;
  }

  function setGenerateStatus(message, tone) {
    const colors = {
      info: "#9fb3c8",
      success: "#b6efc6",
      error: "#ffb8c0",
      busy: "#cfe3ff",
    };
    generateStatusEl.style.color = colors[tone] || colors.info;
    generateStatusEl.textContent = message || "";
  }

  function nowStamp() {
    const d = new Date();
    return d.toLocaleTimeString([], { hour12: false });
  }

  function appendTrace(message) {
    state.traceLines.push(`[${nowStamp()}] ${message}`);
    if (state.traceLines.length > 80) {
      state.traceLines = state.traceLines.slice(-80);
    }
    traceEl.textContent = state.traceLines.join("\n");
    traceEl.scrollTop = traceEl.scrollHeight;
  }

  function clearTrace() {
    state.traceLines = [];
    traceEl.textContent = "";
  }

  function clamp01(value) {
    if (!Number.isFinite(value)) {
      return 0;
    }
    return Math.min(1, Math.max(0, value));
  }

  function formatNumber(value, digits) {
    const num = Number(value);
    if (!Number.isFinite(num)) {
      return "0";
    }
    return num.toFixed(digits);
  }

  function titleize(name) {
    return String(name || "")
      .replace(/_/g, " ")
      .replace(/\b\w/g, (m) => m.toUpperCase());
  }

  function setButtonState() {
    analyzeBtn.disabled = !state.latestFile || state.isAnalyzing;
    generateBtn.disabled = !state.analysis || state.isGenerating || !promptEl.value.trim();
  }

  function splitList(text) {
    return String(text || "")
      .split(/[;,]/)
      .map((part) => part.trim())
      .filter(Boolean);
  }

  function joinList(items) {
    if (!items.length) {
      return "";
    }
    if (items.length === 1) {
      return items[0];
    }
    if (items.length === 2) {
      return `${items[0]} and ${items[1]}`;
    }
    return `${items.slice(0, -1).join(", ")}, and ${items[items.length - 1]}`;
  }

  function cleanLeadClause(firstClause) {
    let text = String(firstClause || "").trim();
    text = text.replace(/\b(track|score|piece|ensemble|groove)\b/gi, " ");
    text = text.replace(/\b(hybrid|electronic|cinematic|ambient|orchestral|jazz|hip-hop|hip hop|rock|funk)\b/gi, " ");
    text = text.replace(/\s+/g, " ").trim();
    return text;
  }

  function composePrompt(basePrompt) {
    const source = String(basePrompt || "").trim();
    if (!source) {
      return "";
    }

    const genreKey = genreEl.value || "auto";
    const preset = GENRE_PRESETS[genreKey] || GENRE_PRESETS.auto;
    const instrumentItems = splitList(instrumentsEl.value);
    if (genreKey === "auto" && !instrumentItems.length) {
      return source;
    }

    const clauses = source
      .split(",")
      .map((part) => part.trim())
      .filter(Boolean);
    const firstClause = clauses.shift() || "";
    const descriptor = cleanLeadClause(firstClause);

    let anchor = "";
    if (genreKey === "auto") {
      anchor = descriptor ? `${descriptor} instrumental track` : "instrumental track";
    } else {
      anchor = `${descriptor ? `${descriptor} ` : ""}${preset.label}`.trim();
    }

    if (instrumentItems.length) {
      anchor += ` with prominent ${joinList(instrumentItems)}`;
    }

    const remainder = clauses.join(", ");
    return remainder ? `${anchor}, ${remainder}` : anchor;
  }

  function applyPromptComposition(reason) {
    const composed = composePrompt(state.basePrompt);
    if (!composed) {
      return;
    }
    promptEl.value = composed;
    if (reason) {
      appendTrace(reason);
    }
    setButtonState();
  }

  function applyGenrePreset(reason) {
    const preset = GENRE_PRESETS[genreEl.value || "auto"] || GENRE_PRESETS.auto;
    instrumentsEl.value = preset.instruments || "";
    applyPromptComposition(reason);
  }

  function renderPromptChoices(topk) {
    promptChoicesEl.innerHTML = "";
    if (!Array.isArray(topk) || !topk.length) {
      return;
    }
    topk.forEach((item) => {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = `Top ${item.rank}: ${item.prototype_name}`;
      button.style.cssText =
        "background:#14263b;border:1px solid #28415c;color:#d9e8ff;padding:6px 9px;border-radius:999px;cursor:pointer;";
      button.addEventListener("click", () => {
        state.basePrompt = item.prompt || "";
        applyPromptComposition(`Prompt switched to prototype ${item.prototype_name}.`);
        setGenerateStatus(`Using prototype ${item.prototype_name} prompt.`, "info");
      });
      promptChoicesEl.appendChild(button);
    });
  }

  function renderSemantics(scores, tags) {
    semanticsEl.innerHTML = "";
    const keys = SEMANTIC_ORDER.filter((key) => Object.prototype.hasOwnProperty.call(scores || {}, `${key}_score`) || Object.prototype.hasOwnProperty.call(scores || {}, key));
    keys.forEach((key) => {
      const scoreKey = Object.prototype.hasOwnProperty.call(scores || {}, `${key}_score`) ? `${key}_score` : key;
      const row = document.createElement("div");
      row.style.cssText = "padding:7px 8px;border-radius:8px;background:#0d1420;border:1px solid #1b2633;";

      const header = document.createElement("div");
      header.style.cssText = "display:flex;justify-content:space-between;gap:8px;align-items:center;margin-bottom:5px;";

      const label = document.createElement("div");
      label.textContent = titleize(key);
      label.style.fontWeight = "600";

      const value = document.createElement("div");
      const score = clamp01(scores[scoreKey]);
      const tagMap = {
        energy: "energy_tag",
        heaviness: "weight_tag",
        sharpness: "attack_tag",
        control: "flow_tag",
        expansiveness: "space_tag",
        rhythmic_stability: "rhythm_tag",
        dynamic: "dynamic_tag",
      };
      const tag = tags && Object.prototype.hasOwnProperty.call(tags, tagMap[key] || "") ? tags[tagMap[key]] : "";
      value.textContent = `${formatNumber(score, 3)}${tag ? ` | ${tag}` : ""}`;
      value.style.color = "#a9bdd5";

      const barWrap = document.createElement("div");
      barWrap.style.cssText = "height:7px;background:#132131;border-radius:999px;overflow:hidden;";
      const bar = document.createElement("div");
      bar.style.cssText = `height:100%;width:${Math.round(score * 100)}%;background:linear-gradient(90deg,#56a4ff,#7df0c7);`;
      barWrap.appendChild(bar);

      header.appendChild(label);
      header.appendChild(value);
      row.appendChild(header);
      row.appendChild(barWrap);
      semanticsEl.appendChild(row);
    });
  }

  function renderPrototypes(topk) {
    prototypesEl.innerHTML = "";
    if (!Array.isArray(topk) || !topk.length) {
      return;
    }

    topk.forEach((item) => {
      const card = document.createElement("div");
      card.style.cssText = "padding:8px;border-radius:8px;background:#0d1420;border:1px solid #1b2633;";

      const line1 = document.createElement("div");
      line1.style.cssText = "display:flex;justify-content:space-between;gap:10px;align-items:center;";
      const left = document.createElement("strong");
      left.textContent = `#${item.rank} ${item.prototype_name}`;
      const right = document.createElement("span");
      right.textContent = `${formatNumber(item.probability, 3)}`;
      right.style.color = "#9fb3c8";
      line1.appendChild(left);
      line1.appendChild(right);

      const phrase = document.createElement("div");
      phrase.textContent = item.prototype_phrase || "";
      phrase.style.cssText = "margin-top:4px;color:#b8cbe0;";

      const useBtn = document.createElement("button");
      useBtn.type = "button";
      useBtn.textContent = "Use this prompt";
      useBtn.style.cssText =
        "margin-top:7px;background:#16324c;border:1px solid #264f75;color:#e7f1ff;padding:5px 8px;border-radius:8px;cursor:pointer;";
      useBtn.addEventListener("click", () => {
        state.basePrompt = item.prompt || "";
        applyPromptComposition(`Prompt loaded from prototype ${item.prototype_name}.`);
        setGenerateStatus(`Loaded ${item.prototype_name} prompt into the editor.`, "info");
      });

      card.appendChild(line1);
      card.appendChild(phrase);
      card.appendChild(useBtn);
      prototypesEl.appendChild(card);
    });
  }

  function renderMeta() {
    if (!state.analysis) {
      const parts = [];
      if (state.latestFile) {
        parts.push(`Latest BVH: ${state.latestFile.name}`);
      }
      if (state.latestSlot) {
        parts.push(`slot ${state.latestSlot}`);
      }
      if (state.latestLoadedMeta) {
        parts.push(`${state.latestLoadedMeta.numFrames || 0} frames`);
      }
      if (state.health && state.health.musicgen_device) {
        parts.push(`MusicGen: ${state.health.musicgen_device}`);
      }
      metaEl.textContent = parts.join(" | ") || "Upload a BVH in the viewer. The latest uploaded BVH will be analyzed automatically.";
      return;
    }

    const motion = state.analysis.motion || {};
    const extractor = state.analysis.extractor || {};
    const parts = [
      state.analysis.bvh_name || "unknown.bvh",
      `${formatNumber(motion.duration_s, 2)}s`,
      `${formatNumber(motion.fps, 2)} FPS`,
      `${motion.frame_count || 0} frames`,
      `${motion.beat_count || 0} beats`,
      `LMA: ${extractor.lma_mode || "unknown"}`,
      `BPM: ${formatNumber(state.analysis.bpm, 1)}`,
    ];
    if (state.health && state.health.musicgen_device) {
      parts.push(`MusicGen: ${state.health.musicgen_device}`);
    }
    if (extractor.warning) {
      parts.push("repo fallback used");
    }
    metaEl.textContent = parts.join(" | ");
  }

  function renderAnalysis(payload) {
    state.analysis = payload;
    state.basePrompt = payload.prompt_top1 || payload.base_prompt || "";
    applyPromptComposition();
    renderPromptChoices(payload.topk || []);
    renderSemantics(payload.semantic_scores || {}, payload.semantic_tags || {});
    renderPrototypes(payload.topk || []);
    renderMeta();
    audioLinkEl.style.display = "none";
    audioLinkEl.removeAttribute("href");
    setStatus(`Analysis ready. Top prototype: ${payload.topk && payload.topk[0] ? payload.topk[0].prototype_name : "unknown"}.`, "success");
    setGenerateStatus("Prompt is ready. Edit it if you want, then press Generate music.", "info");
    appendTrace(`Analysis complete. Top prototype: ${payload.topk && payload.topk[0] ? payload.topk[0].prototype_name : "unknown"}.`);
    if (payload.extractor && payload.extractor.warning) {
      appendTrace(`Extractor warning: ${payload.extractor.warning}`);
    }
    setButtonState();
  }

  async function analyzeLatestFile() {
    if (!state.latestFile || state.isAnalyzing) {
      return;
    }
    state.isAnalyzing = true;
    state.analysis = null;
    const token = ++state.analyzeToken;
    setButtonState();
    setStatus(`Analyzing ${state.latestFile.name}...`, "busy");
    setGenerateStatus("", "info");
    promptChoicesEl.innerHTML = "";
    semanticsEl.innerHTML = "";
    prototypesEl.innerHTML = "";
    audioLinkEl.style.display = "none";
    clearTrace();
    appendTrace(`Selected BVH ${state.latestFile.name}.`);
    appendTrace("Uploading BVH to backend.");
    appendTrace("Running LMA extraction and beat detection.");

    const formData = new FormData();
    formData.append("bvh", state.latestFile, state.latestFile.name);

    try {
      const response = await fetch("/api/analyze-bvh?top_k=3", {
        method: "POST",
        body: formData,
      });
      const payload = await response.json();
      if (!response.ok || !payload.ok) {
        throw new Error(payload.error || `Analyze failed (${response.status})`);
      }
      if (token !== state.analyzeToken) {
        return;
      }
      appendTrace("Computing semantic scores and prototype ranking.");
      renderAnalysis(payload);
    } catch (error) {
      setStatus(`Analyze failed: ${error.message}`, "error");
      setGenerateStatus("Make sure the Motion2Music web server is running, then try again.", "error");
      appendTrace(`Analyze failed: ${error.message}`);
    } finally {
      state.isAnalyzing = false;
      setButtonState();
    }
  }

  function stopJobPolling() {
    if (state.jobPollHandle) {
      window.clearInterval(state.jobPollHandle);
      state.jobPollHandle = null;
    }
  }

  async function pollJobStatus(jobId) {
    if (!jobId) {
      return;
    }
    try {
      const response = await fetch(`/api/job-status?job_id=${encodeURIComponent(jobId)}`, { cache: "no-store" });
      const payload = await response.json();
      if (!response.ok || !payload.ok) {
        throw new Error(payload.error || `Job status failed (${response.status})`);
      }

      const progressPct = Math.round((Number(payload.progress) || 0) * 100);
      if (payload.message) {
        setStatus(`MusicGen: ${payload.message}`, payload.status === "failed" ? "error" : payload.status === "completed" ? "success" : "busy");
      }
      let details = payload.message || "Working...";
      if (payload.eta_note) {
        details += ` ${payload.eta_note}`;
      }
      if (payload.quality && payload.model_id) {
        details += ` [${payload.quality} | ${payload.model_id.split("/").pop()}]`;
      }
      details += ` (${progressPct}%)`;
      setGenerateStatus(details, payload.status === "failed" ? "error" : payload.status === "completed" ? "success" : "busy");

      if (Array.isArray(payload.trace)) {
        const mapped = payload.trace.map((entry) => {
          const d = new Date((entry.ts || 0) * 1000);
          const stamp = Number.isFinite(d.getTime())
            ? d.toLocaleTimeString([], { hour12: false })
            : nowStamp();
          return `[${stamp}] ${entry.message}`;
        });
        state.traceLines = mapped.slice(-80);
        traceEl.textContent = state.traceLines.join("\n");
        traceEl.scrollTop = traceEl.scrollHeight;
      }

      if (payload.status === "completed" && payload.result) {
        stopJobPolling();
        state.isGenerating = false;
        state.generationJobId = null;
        setButtonState();
        const result = payload.result;
        if (result.fallback_model_id) {
          appendTrace(`Requested best quality fell back to ${result.effective_quality || "better"} because the large model could not load on this setup.`);
        }

        if (window.m2mMusicSync && typeof window.m2mMusicSync.loadAudioSource === "function") {
          window.m2mMusicSync.loadAudioSource(result.audio_url, result.audio_name || result.audio_url);
          if (typeof window.m2mMusicSync.setLog === "function") {
            window.m2mMusicSync.setLog(`Generated audio loaded: ${result.audio_name || result.audio_url}`);
          }
        }

        audioLinkEl.href = result.audio_url;
        audioLinkEl.textContent = result.audio_name || "Open generated audio";
        audioLinkEl.style.display = "";

        setStatus("Music generation complete. The audio is loaded into the player.", "success");
        setGenerateStatus("Generated audio is ready in the Music panel. Press play to compare it against the BVH.", "success");
        appendTrace("Generated audio loaded into the synced player.");
      } else if (payload.status === "failed") {
        stopJobPolling();
        state.isGenerating = false;
        state.generationJobId = null;
        setButtonState();
        setStatus(`Generation failed: ${payload.error || payload.message || "unknown error"}`, "error");
        setGenerateStatus("Generation failed. Check the trace panel for details.", "error");
        appendTrace(`Generation failed: ${payload.error || payload.message || "unknown error"}`);
      }
    } catch (error) {
      stopJobPolling();
      state.isGenerating = false;
      state.generationJobId = null;
      setButtonState();
      setStatus(`Generation status check failed: ${error.message}`, "error");
      setGenerateStatus("Lost contact with the backend while generating.", "error");
      appendTrace(`Job polling failed: ${error.message}`);
    }
  }

  async function generateMusic() {
    const prompt = promptEl.value.trim();
    if (!prompt || state.isGenerating) {
      return;
    }
    state.isGenerating = true;
    setButtonState();
    audioLinkEl.style.display = "none";
    const quality = qualityEl.value || "preview";
    appendTrace(`Submitting ${QUALITY_LABELS[quality] || quality} MusicGen job for ${Number(durationEl.value) || 8}s audio.`);

    try {
      const response = await fetch("/api/generate-music", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          session_id: state.analysis ? state.analysis.session_id : null,
          prompt,
          duration: Number(durationEl.value) || 8,
          seed: Number(seedEl.value) || 1234,
          quality,
        }),
      });
      const payload = await response.json();
      if (!response.ok || !payload.ok) {
        throw new Error(payload.error || `Generate failed (${response.status})`);
      }

      state.generationJobId = payload.job_id;
      setStatus("MusicGen job started.", "busy");
      const durationValue = Number(durationEl.value) || 8;
      const device = state.health && state.health.musicgen_device ? state.health.musicgen_device : "unknown device";
      const qualityLabel = QUALITY_LABELS[quality] || quality;
      if (device === "cpu" && (durationValue > 12 || quality !== "preview")) {
        setGenerateStatus(`${qualityLabel} quality on CPU can take a long time.`, "busy");
      } else {
        setGenerateStatus("Job submitted. First run of a new quality may spend time downloading/loading model weights.", "busy");
      }
      appendTrace(`MusicGen job ${payload.job_id} queued with quality ${qualityLabel}.`);
      stopJobPolling();
      state.jobPollHandle = window.setInterval(() => {
        pollJobStatus(payload.job_id);
      }, 1500);
      pollJobStatus(payload.job_id);
    } catch (error) {
      state.isGenerating = false;
      state.generationJobId = null;
      setButtonState();
      setStatus(`Generation failed: ${error.message}`, "error");
      setGenerateStatus("Generation failed. Check that the server is still running and try again.", "error");
      appendTrace(`Generate request failed: ${error.message}`);
    }
  }

  async function checkHealth() {
    try {
      const response = await fetch("/api/health", { cache: "no-store" });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const payload = await response.json();
      state.health = payload;
      setStatus("Web pipeline connected. Upload a BVH to start.", "info");
      const pieces = [];
      if (payload.model_bundle) {
        pieces.push(`model: ${payload.model_bundle.split(/[\\/]/).pop()}`);
      }
      if (payload.lma_repo) {
        pieces.push("LMA repo found");
      } else {
        pieces.push("simple LMA fallback ready");
      }
      if (payload.musicgen_device) {
        pieces.push(`MusicGen: ${payload.musicgen_device}`);
      }
      if (payload.torch_version) {
        pieces.push(`Torch: ${payload.torch_version}`);
      }
      metaEl.textContent = pieces.join(" | ");
      appendTrace(`Backend ready. MusicGen device: ${payload.musicgen_device || "unknown"}.`);
      if (!payload.torch_cuda_available) {
        appendTrace("Torch is CPU-only right now, so GPU generation is unavailable until the Python environment is updated.");
      }
    } catch (error) {
      setStatus("Pipeline backend is not reachable yet.", "warn");
      metaEl.textContent = "Start scripts/motion2music_web_server.py, then reload this page.";
      appendTrace("Backend not reachable.");
    }
  }

  analyzeBtn.addEventListener("click", () => {
    analyzeLatestFile();
  });

  generateBtn.addEventListener("click", () => {
    generateMusic();
  });

  promptEl.addEventListener("input", () => {
    setButtonState();
  });

  genreEl.addEventListener("change", () => {
    const label = genreEl.options[genreEl.selectedIndex] ? genreEl.options[genreEl.selectedIndex].text : genreEl.value;
    applyGenrePreset(`Genre anchor changed to ${label}.`);
  });

  qualityEl.addEventListener("change", () => {
    const label = qualityEl.options[qualityEl.selectedIndex] ? qualityEl.options[qualityEl.selectedIndex].text : qualityEl.value;
    appendTrace(`Quality changed to ${label}.`);
  });

  instrumentsEl.addEventListener("input", () => {
    applyPromptComposition("Instrument anchor updated.");
  });

  toggleBtn.addEventListener("click", () => {
    const hidden = bodyEl.style.display === "none";
    bodyEl.style.display = hidden ? "" : "none";
    toggleBtn.textContent = hidden ? "-" : "+";
  });

  window.addEventListener("m2m:bvh-file-selected", (event) => {
    const detail = event.detail || {};
    state.latestFile = detail.file || null;
    state.latestSlot = detail.bvhReaderId || null;
    state.latestLoadedMeta = null;
    state.analysis = null;
    state.basePrompt = "";
    stopJobPolling();
    state.generationJobId = null;
    renderMeta();
    setStatus(`BVH selected: ${detail.fileName || "upload.bvh"}. Starting analysis...`, "busy");
    setGenerateStatus("", "info");
    setButtonState();
    analyzeLatestFile();
  });

  window.addEventListener("m2m:bvh-loaded", (event) => {
    const detail = event.detail || {};
    state.latestLoadedMeta = detail;
    renderMeta();
    appendTrace(`BVH loaded into viewer at ${formatNumber(detail.nativeFps, 2)} FPS.`);
  });

  clearTrace();
  appendTrace("Motion2Music panel initialized.");
  checkHealth();
  setButtonState();

  window.addEventListener("beforeunload", () => {
    stopJobPolling();
  });
})();
