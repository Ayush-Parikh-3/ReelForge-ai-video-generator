/**
 * ReelForge • Ultra-Clean Minimalist AI Text-to-Video Studio
 * Frontend controller with SSE streaming, keys persistence, and mobile responsiveness
 */

document.addEventListener("DOMContentLoaded", () => {
  // DOM Elements
  const promptInput = document.getElementById("promptInput");
  const charCount = document.getElementById("charCount");
  const voiceSelect = document.getElementById("voiceSelect");
  const sceneCountSelect = document.getElementById("sceneCountSelect");
  const subtitleStyleSelect = document.getElementById("subtitleStyleSelect");
  const musicCheck = document.getElementById("musicCheck");
  const btnGenerate = document.getElementById("btnGenerate");
  const btnMobileGenerate = document.getElementById("btnMobileGenerate");
  const btnGenerateText = document.getElementById("btnGenerateText");
  const ratioGroup = document.getElementById("ratioGroup");

  // Progress Section
  const promptSection = document.getElementById("promptSection");
  const progressSection = document.getElementById("progressSection");
  const progressStatusText = document.getElementById("progressStatusText");
  const progressSubText = document.getElementById("progressSubText");
  const progressPercent = document.getElementById("progressPercent");
  const progressBarFill = document.getElementById("progressBarFill");

  // Stepper Items
  const stepScript = document.getElementById("stepScript");
  const stateScript = document.getElementById("stateScript");
  const stepVoice = document.getElementById("stepVoice");
  const stateVoice = document.getElementById("stateVoice");
  const stepFootage = document.getElementById("stepFootage");
  const stateFootage = document.getElementById("stateFootage");
  const stepAssembly = document.getElementById("stepAssembly");
  const stateAssembly = document.getElementById("stateAssembly");

  // Results Section
  const resultSection = document.getElementById("resultSection");
  const resultVideoTitle = document.getElementById("resultVideoTitle");
  const resultVideoMeta = document.getElementById("resultVideoMeta");
  const videoPlayer = document.getElementById("videoPlayer");
  const videoSource = document.getElementById("videoSource");
  const videoTrack = document.getElementById("videoTrack");
  const videoFrameWrapper = document.getElementById("videoFrameWrapper");
  const btnDownloadVideo = document.getElementById("btnDownloadVideo");
  const btnNewVideo = document.getElementById("btnNewVideo");
  const scenesList = document.getElementById("scenesList");

  // Modal Elements
  const btnOpenKeys = document.getElementById("btnOpenKeys");
  const btnCloseModal = document.getElementById("btnCloseModal");
  const keysModal = document.getElementById("keysModal");
  const inputGeminiKey = document.getElementById("inputGeminiKey");
  const inputPixabayKey = document.getElementById("inputPixabayKey");
  const btnTestKeys = document.getElementById("btnTestKeys");
  const testKeysSpinner = document.getElementById("testKeysSpinner");
  const btnSaveKeys = document.getElementById("btnSaveKeys");
  const geminiStatusMsg = document.getElementById("geminiStatusMsg");
  const pixabayStatusMsg = document.getElementById("pixabayStatusMsg");
  const keysStatusDot = document.getElementById("keysStatusDot");
  const toast = document.getElementById("toast");

  let activeEventSource = null;
  let activeJobId = null;
  let jobPollInterval = null;
  let pollErrorCount = 0;
  const MAX_POLL_RETRIES = 15;
  let serverHasGemini = false;
  let serverHasPixabay = false;

  // 1. Initial State & Keys Loading from LocalStorage (Client-Side BYOK)
  function loadSavedKeys() {
    const savedGemini = localStorage.getItem("reelforge_gemini_key") || localStorage.getItem("cineforge_gemini_key") || "";
    const savedPixabay = localStorage.getItem("reelforge_pixabay_key") || localStorage.getItem("cineforge_pixabay_key") || "";

    if (savedGemini && inputGeminiKey) inputGeminiKey.value = savedGemini;
    if (savedPixabay && inputPixabayKey) inputPixabayKey.value = savedPixabay;

    updateKeysStatus();
  }

  function updateKeysStatus() {
    const hasGemini = Boolean((localStorage.getItem("reelforge_gemini_key") || localStorage.getItem("cineforge_gemini_key") || "").trim() || serverHasGemini);
    const hasPixabay = Boolean((localStorage.getItem("reelforge_pixabay_key") || localStorage.getItem("cineforge_pixabay_key") || "").trim() || serverHasPixabay);

    if (hasGemini && hasPixabay) {
      keysStatusDot.classList.add("active");
    } else {
      keysStatusDot.classList.remove("active");
    }
  }

  // 2. Fetch server configuration
  async function fetchConfig() {
    try {
      const res = await fetch("/api/config");
      if (res.ok) {
        const data = await res.json();
        serverHasGemini = Boolean(data.has_server_gemini_key);
        serverHasPixabay = Boolean(data.has_server_pixabay_key);

        if (serverHasGemini && inputGeminiKey && !inputGeminiKey.value) {
          inputGeminiKey.placeholder = "Configured in server environment (optional to override)";
          if (geminiStatusMsg) {
            geminiStatusMsg.textContent = "Active via server environment variable. You can enter your own key to override.";
            geminiStatusMsg.className = "key-hint-msg success";
          }
        }
        if (serverHasPixabay && inputPixabayKey && !inputPixabayKey.value) {
          inputPixabayKey.placeholder = "Configured in server environment (optional to override)";
          if (pixabayStatusMsg) {
            pixabayStatusMsg.textContent = "Active via server environment variable. You can enter your own key to override.";
            pixabayStatusMsg.className = "key-hint-msg success";
          }
        }

        updateKeysStatus();

        if (data.voices && data.voices.length > 0) {
          voiceSelect.innerHTML = "";
          data.voices.forEach(v => {
            const opt = document.createElement("option");
            opt.value = v.id;
            opt.textContent = v.name;
            voiceSelect.appendChild(opt);
          });
        }
      }
    } catch (e) {
      console.warn("Config load warning:", e);
    }
  }

  // 3. Prompt & Character Counter
  promptInput.addEventListener("input", () => {
    charCount.textContent = `${promptInput.value.length} / 2000`;
  });

  // 4. Preset Inspiration Chips
  document.querySelectorAll(".chip").forEach(chip => {
    chip.addEventListener("click", () => {
      promptInput.value = chip.dataset.prompt;
      charCount.textContent = `${promptInput.value.length} / 2000`;
      promptInput.focus();
    });
  });

  // 5. Aspect Ratio Toggle
  ratioGroup.querySelectorAll(".radio-option").forEach(label => {
    label.addEventListener("click", () => {
      ratioGroup.querySelectorAll(".radio-option").forEach(l => l.classList.remove("active"));
      label.classList.add("active");
    });
  });

  function getSelectedAspectRatio() {
    const checked = ratioGroup.querySelector('input[name="aspectRatio"]:checked');
    return checked ? checked.value : "16:9";
  }

  // 6. Keys Modal Logic
  btnOpenKeys.addEventListener("click", () => keysModal.classList.remove("hidden"));
  btnCloseModal.addEventListener("click", () => keysModal.classList.add("hidden"));
  keysModal.addEventListener("click", (e) => {
    if (e.target === keysModal) keysModal.classList.add("hidden");
  });

  // Toggle key visibility
  document.querySelectorAll(".btn-toggle-eye").forEach(btn => {
    btn.addEventListener("click", () => {
      const targetId = btn.dataset.target;
      const input = document.getElementById(targetId);
      if (input.type === "password") {
        input.type = "text";
        btn.style.color = "var(--text-primary)";
      } else {
        input.type = "password";
        btn.style.color = "var(--text-muted)";
      }
    });
  });

  // Test Keys
  btnTestKeys.addEventListener("click", async () => {
    testKeysSpinner.classList.remove("hidden");
    btnTestKeys.disabled = true;
    if (geminiStatusMsg) {
      geminiStatusMsg.textContent = "Verifying...";
      geminiStatusMsg.className = "key-hint-msg";
    }
    if (pixabayStatusMsg) {
      pixabayStatusMsg.textContent = "Verifying...";
      pixabayStatusMsg.className = "key-hint-msg";
    }

    try {
      const res = await fetch("/api/test-keys", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          gemini_api_key: inputGeminiKey ? inputGeminiKey.value.trim() : "",
          pixabay_api_key: inputPixabayKey ? inputPixabayKey.value.trim() : ""
        })
      });

      const data = await res.json();
      testKeysSpinner.classList.add("hidden");
      btnTestKeys.disabled = false;

      if (data.gemini && geminiStatusMsg) {
        geminiStatusMsg.textContent = data.gemini.message;
        geminiStatusMsg.className = `key-hint-msg ${data.gemini.valid ? "success" : "error"}`;
      }
      if (data.pixabay && pixabayStatusMsg) {
        pixabayStatusMsg.textContent = data.pixabay.message;
        pixabayStatusMsg.className = `key-hint-msg ${data.pixabay.valid ? "success" : "error"}`;
      }
    } catch (err) {
      testKeysSpinner.classList.add("hidden");
      btnTestKeys.disabled = false;
      showToast("Network error while testing keys.");
    }
  });

  // Save Keys (Browser LocalStorage Only - Zero Server Storage)
  btnSaveKeys.addEventListener("click", () => {
    const geminiKey = inputGeminiKey ? inputGeminiKey.value.trim() : "";
    const pixabayKey = inputPixabayKey ? inputPixabayKey.value.trim() : "";

    if (geminiKey) {
      localStorage.setItem("reelforge_gemini_key", geminiKey);
    } else {
      localStorage.removeItem("reelforge_gemini_key");
      localStorage.removeItem("cineforge_gemini_key");
    }

    if (pixabayKey) {
      localStorage.setItem("reelforge_pixabay_key", pixabayKey);
    } else {
      localStorage.removeItem("reelforge_pixabay_key");
      localStorage.removeItem("cineforge_pixabay_key");
    }

    updateKeysStatus();
    keysModal.classList.add("hidden");
    showToast("Keys saved securely in your browser!");
  });

  // 7. Toast Message Helper
  function showToast(msg) {
    toast.textContent = msg;
    toast.classList.remove("hidden");
    setTimeout(() => toast.classList.add("hidden"), 3500);
  }

  // 8. Stepper Update Helper
  function resetStepper() {
    [stepScript, stepVoice, stepFootage, stepAssembly].forEach(el => {
      el.className = "step-item";
    });
    stateScript.textContent = "Pending";
    stateVoice.textContent = "Pending";
    stateFootage.textContent = "Pending";
    stateAssembly.textContent = "Pending";
    progressBarFill.style.width = "0%";
    progressPercent.textContent = "0%";
  }

  function updateStage(stage, pct, message) {
    progressBarFill.style.width = `${pct}%`;
    progressPercent.textContent = `${pct}%`;
    progressSubText.textContent = message;

    if (stage === "script") {
      stepScript.classList.add("active");
      stateScript.textContent = "Writing...";
    } else if (stage === "voice") {
      stepScript.className = "step-item completed";
      stateScript.textContent = "Done";
      stepVoice.classList.add("active");
      stateVoice.textContent = "Speaking...";
    } else if (stage === "footage") {
      stepVoice.className = "step-item completed";
      stateVoice.textContent = "Done";
      stepFootage.classList.add("active");
      stateFootage.textContent = "Searching...";
    } else if (stage === "rendering" || stage === "assembly" || stage === "audio") {
      stepFootage.className = "step-item completed";
      stateFootage.textContent = "Done";
      stepAssembly.classList.add("active");
      stateAssembly.textContent = "Assembling...";
    } else if (stage === "complete" || stage === "done") {
      [stepScript, stepVoice, stepFootage, stepAssembly].forEach(el => {
        el.className = "step-item completed";
      });
      stateScript.textContent = "Done";
      stateVoice.textContent = "Done";
      stateFootage.textContent = "Done";
      stateAssembly.textContent = "Done";
    }
  }

  // 9. Start Generation Flow
  async function startGeneration() {
    const prompt = promptInput.value.trim();
    if (!prompt) {
      showToast("Please enter a topic or story prompt first.");
      promptInput.focus();
      return;
    }

    const geminiKey = (localStorage.getItem("reelforge_gemini_key") || localStorage.getItem("cineforge_gemini_key") || "").trim();
    const pixabayKey = (localStorage.getItem("reelforge_pixabay_key") || localStorage.getItem("cineforge_pixabay_key") || "").trim();

    // Keys are completely optional: server environment variables will power generation by default.
    // If the user entered custom keys, they will override the server defaults.

    const sceneCount = parseInt(sceneCountSelect.value, 10);
    const aspectRatio = getSelectedAspectRatio();
    const voiceId = voiceSelect.value;
    const subtitleStyle = subtitleStyleSelect.value;
    const includeMusic = musicCheck.checked;

    // Switch UI to Progress view
    promptSection.classList.add("hidden");
    resultSection.classList.add("hidden");
    progressSection.classList.remove("hidden");
    resetStepper();
    btnGenerate.disabled = true;
    btnMobileGenerate.disabled = true;

    // Scroll to top smoothly
    window.scrollTo({ top: 0, behavior: "smooth" });

    // Clear any previous active polling or streams
    if (jobPollInterval) {
      clearInterval(jobPollInterval);
      jobPollInterval = null;
    }
    if (activeEventSource) {
      activeEventSource.close();
      activeEventSource = null;
    }
    activeJobId = null;
    pollErrorCount = 0;

    // Start video generation job via robust REST endpoint
    try {
      const response = await fetch("/api/start-generation", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt: prompt,
          scene_count: sceneCount,
          aspect_ratio: aspectRatio,
          voice_id: voiceId,
          subtitle_style: subtitleStyle,
          include_music: includeMusic,
          gemini_api_key: geminiKey,
          pixabay_api_key: pixabayKey
        })
      });

      if (!response.ok) {
        let errMessage = "Failed to start generation.";
        try {
          const errData = await response.json();
          if (errData && errData.detail) errMessage = errData.detail;
        } catch (_) {}
        handleGenerationError(errMessage);
        return;
      }

      const data = await response.json();
      activeJobId = data.job_id;

      // Resilient background polling: immune to mobile SSE disconnects and proxy drops
      jobPollInterval = setInterval(async () => {
        if (!activeJobId) {
          clearInterval(jobPollInterval);
          return;
        }

        try {
          const pollRes = await fetch(`/api/job-status/${activeJobId}`);
          if (!pollRes.ok) {
            if (pollRes.status === 404) {
              clearInterval(jobPollInterval);
              handleGenerationError("Generation session expired. Please try again.");
              return;
            }
            throw new Error(`HTTP ${pollRes.status}`);
          }

          const job = await pollRes.json();
          pollErrorCount = 0; // Reset network error count on successful poll

          if (job.status === "error") {
            clearInterval(jobPollInterval);
            handleGenerationError(job.error || "An error occurred during video creation.");
            return;
          }

          if (job.status === "done") {
            clearInterval(jobPollInterval);
            handleGenerationSuccess(job.result);
            return;
          }

          // Update progress stepper and bar
          updateStage(job.stage, job.percent, job.message);

        } catch (pollErr) {
          pollErrorCount++;
          console.warn(`Temporary mobile network hiccup (${pollErrorCount}/${MAX_POLL_RETRIES}):`, pollErr);
          if (pollErrorCount >= MAX_POLL_RETRIES) {
            clearInterval(jobPollInterval);
            handleGenerationError("Network connection lost. Please check your internet connection.");
          }
        }
      }, 1000);

    } catch (startErr) {
      console.error("Start generation network error:", startErr);
      handleGenerationError("Unable to reach server. Please check your internet connection.");
    }
  }

  function handleGenerationSuccess(result) {
    if (jobPollInterval) {
      clearInterval(jobPollInterval);
      jobPollInterval = null;
    }
    activeJobId = null;
    progressSection.classList.add("hidden");
    resultSection.classList.remove("hidden");
    btnGenerate.disabled = false;
    btnMobileGenerate.disabled = false;

    // Configure video player
    resultVideoTitle.textContent = result.title || "Finished Video";
    resultVideoMeta.textContent = `Duration: ${result.duration}s • Format: ${result.aspect_ratio}`;

    // Aspect ratio container adjustment
    if (result.aspect_ratio === "9:16") {
      videoFrameWrapper.classList.add("portrait");
    } else {
      videoFrameWrapper.classList.remove("portrait");
    }

    // Set video sources with cache buster
    const cacheBuster = `?t=${Date.now()}`;
    videoSource.src = `${result.video_url}${cacheBuster}`;
    videoTrack.src = `${result.vtt_url}${cacheBuster}`;

    videoPlayer.load();
    videoPlayer.play().catch(() => {
      // Autoplay with audio might require user click; controls are available
    });

    // Configure download buttons
    btnDownloadVideo.href = result.video_url;
    btnDownloadVideo.setAttribute("download", `${(result.title || "video").replace(/\s+/g, "_")}.mp4`);

    // Render Scene Breakdown
    scenesList.innerHTML = "";
    if (result.scenes && result.scenes.length > 0) {
      result.scenes.forEach(s => {
        const card = document.createElement("div");
        card.className = "scene-item-card";

        const sourceLabel = s.visual_source === "pixabay_video" 
          ? "Pixabay Stock Video" 
          : s.visual_source === "pixabay_photo"
            ? "Pixabay Stock Photo (Motion)"
            : "Safe Stock Visual";

        card.innerHTML = `
          <div class="scene-card-top">
            <span class="scene-badge">Scene ${s.scene_id} • ${s.duration ? s.duration.toFixed(1) : 4}s</span>
            <span class="scene-footage-source">${sourceLabel}</span>
          </div>
          <p class="scene-narration">"${s.narration}"</p>
          <span class="scene-query">Search query: <strong>${s.stock_query}</strong></span>
        `;
        scenesList.appendChild(card);
      });
    }

    showToast("Video created successfully!");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function handleGenerationError(errMsg) {
    if (jobPollInterval) {
      clearInterval(jobPollInterval);
      jobPollInterval = null;
    }
    activeJobId = null;
    progressSection.classList.add("hidden");
    promptSection.classList.remove("hidden");
    btnGenerate.disabled = false;
    btnMobileGenerate.disabled = false;
    showToast(errMsg);
  }

  // 10. Reset for New Video
  btnNewVideo.addEventListener("click", () => {
    if (jobPollInterval) {
      clearInterval(jobPollInterval);
      jobPollInterval = null;
    }
    activeJobId = null;
    videoPlayer.pause();
    resultSection.classList.add("hidden");
    promptSection.classList.remove("hidden");
    promptInput.value = "";
    charCount.textContent = "0 / 2000";
    promptInput.focus();
    window.scrollTo({ top: 0, behavior: "smooth" });
  });

  // 11. Event Listeners for Generation
  btnGenerate.addEventListener("click", startGeneration);
  btnMobileGenerate.addEventListener("click", startGeneration);

  // Keyboard shortcut: Ctrl+Enter or Cmd+Enter
  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      if (!promptSection.classList.contains("hidden")) {
        startGeneration();
      }
    }
  });

  // Initialize
  loadSavedKeys();
  fetchConfig();
});
