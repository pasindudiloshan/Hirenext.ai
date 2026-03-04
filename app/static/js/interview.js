/* static/js/interview.js — UPDATED (Popup Results + new flow + nicer popup size) ✅
   ✅ Timer, cam/mic toggles, optional screen-record download
   ✅ NEW interview flow:
      - Auto TTS on each question
      - Record button toggles: start -> stop -> auto submit -> auto next
      - During interview: no rubric breakdown UI
      - AI panel shows LOADING DOTS while processing

   ✅ NEW RESULTS POPUP:
      - End button opens results in centered popup (separate page)
      - When last question completes, tries to open popup (fallback redirect)

   ✅ POPUP SIZE:
      - Fixed 1180x760 (similar to your screenshot)
      - Attempts to hide toolbar/menubar/location (browser may ignore some)

   ✅ IMPORTANT:
      - Uses window.openCenteredPopup from interview.html IF available
      - Has internal fallback popup helper if not available
*/

document.addEventListener("DOMContentLoaded", () => {
  // ---------------- Elements ----------------
  const el = {
    timer: document.getElementById("ivTimer"),
    recDot: document.getElementById("ivRecDot"),
    recText: document.getElementById("ivRecText"),
    aiRing: document.getElementById("aiRing"),

    video: document.getElementById("candidateVideo"),
    overlay: document.getElementById("videoOverlay"),

    // Optional transcript text (hidden in HTML by default)
    transcriptNow: document.getElementById("transcriptNow"),

    // ✅ AI loading dots
    aiDots: document.getElementById("aiDots"),

    btnToggleCam: document.getElementById("btnToggleCam"),
    btnToggleMic: document.getElementById("btnToggleMic"),
    btnRecord: document.getElementById("btnRecord"), // screen record (optional)

    qMeta: document.getElementById("qMeta"),
    qText: document.getElementById("qText"),
    scoreLine: document.getElementById("scoreLine"),

    btnRecAns: document.getElementById("btnRecAns"),

    // ✅ End interview button (popup results)
    btnEnd: document.getElementById("btnEndInterview"),
  };

  // ---------------- Context ----------------
  const ctxAi = window.__INTERVIEW_AI_CTX__ || {};
  const ctxLegacy = window.__INTERVIEW_CTX__ || {};
  const hasOptionAI = !!(el.btnRecAns || el.qText);

  // ---------------- State ----------------
  const state = {
    startedAt: Date.now(),
    timerT: null,

    // cam/mic preview stream (video+audio)
    camStream: null,
    camOn: false,
    micOn: false,

    // screen recording (optional)
    recOn: false,
    screenStream: null,
    screenRecorder: null,
    recChunks: [],

    // answer recording (audio only)
    ansRecOn: false,
    ansStream: null,
    ansRecorder: null,
    ansChunks: [],
    lastAnswerBlob: null,

    // submitting lock
    submitting: false,

    // question flow
    questions: Array.isArray(ctxAi.questions) ? ctxAi.questions : [],
    role: String(ctxAi.role || ""),
    interviewId: String(ctxAi.interviewId || ctxAi.sessionId || ctxLegacy.interviewId || ""),
    submitUrl: String(ctxAi.submitUrl || "/interview-ai/submit-answer"),
    resultsUrl: String(ctxAi.resultsUrl || ""),
    qIndex: 0,

    // UX tuning
    autoSpeakDelayMs: 350,
    autoNextDelayMs: 350,

    // Results popup: ensure we open once
    resultsOpened: false,
  };

  // ---------------- Utils ----------------
  const pad = (n) => String(n).padStart(2, "0");
  function fmtTime(ms) {
    const s = Math.max(0, Math.floor(ms / 1000));
    const mm = Math.floor(s / 60);
    const ss = s % 60;
    return `${pad(mm)}:${pad(ss)}`;
  }

  function startTimer() {
    if (state.timerT) return;
    state.startedAt = Date.now();
    state.timerT = setInterval(() => {
      if (el.timer) el.timer.textContent = fmtTime(Date.now() - state.startedAt);
    }, 500);
  }
  startTimer();

  // ---------------- Centered popup helper ----------------
  // Prefer the global helper from interview.html (window.openCenteredPopup),
  // but keep a fallback here so interview.js never breaks.
  function openCenteredPopupFallback(url, { fallbackToRedirect = true } = {}) {
    if (!url) return null;

    // ✅ Fixed size like your screenshot
    const w = 1180;
    const h = 760;

    const left = Math.floor((window.screen.width - w) / 2);
    const top = Math.floor((window.screen.height - h) / 2);

    // ✅ Try to reduce chrome (browser may ignore some options)
    const features = [
      `width=${w}`,
      `height=${h}`,
      `left=${left}`,
      `top=${top}`,
      "resizable=yes",
      "scrollbars=yes",
      "toolbar=no",
      "menubar=no",
      "location=no",
      "status=no",
    ].join(",");

    const win = window.open(url, "InterviewResults", features);

    // Popup blocked → fallback
    if (!win || win.closed || typeof win.closed === "undefined") {
      if (fallbackToRedirect) window.location.href = url;
      return null;
    }

    win.focus();
    return win;
  }

  function openCenteredPopup(url, opts) {
    // ✅ If you defined window.openCenteredPopup in interview.html, use it
    if (typeof window.openCenteredPopup === "function") {
      const win = window.openCenteredPopup(url);
      // If popup blocked, interview.html helper already redirects; just return
      return win;
    }
    // else use fallback that supports the same behavior
    return openCenteredPopupFallback(url, opts);
  }

  function openResultsOnce() {
    if (state.resultsOpened) return;
    if (!state.resultsUrl) return;

    state.resultsOpened = true;

    // Auto-open may be blocked (not user gesture). Fallback redirect ensures results show.
    openCenteredPopup(state.resultsUrl, { fallbackToRedirect: true });
  }

  // ---------------- AI loading dots control ----------------
  function setAiLoading(isLoading) {
    if (el.aiDots) el.aiDots.style.display = isLoading ? "flex" : "none";

    if (el.aiRing) {
      el.aiRing.style.boxShadow = isLoading
        ? "0 0 0 14px rgba(56,189,248,.16)"
        : "0 0 0 0 rgba(56,189,248,0)";
    }
  }
  setAiLoading(false);

  // ---------------- Optional transcript helper ----------------
  function setTranscriptNow(text) {
    if (!el.transcriptNow) return;
    el.transcriptNow.textContent = String(text || "");
  }
  window.setTranscriptNow = setTranscriptNow;

  function setScoreLine(text) {
    if (!el.scoreLine) return;
    el.scoreLine.textContent = String(text || "");
  }

  function setControlsEnabled({ record }) {
    if (el.btnRecAns) el.btnRecAns.disabled = !record;
  }

  // ---------------- Screen-record UI pill ----------------
  function setRec(on) {
    state.recOn = on;
    if (!el.recText || !el.recDot) return;

    el.recText.textContent = on ? "REC ON" : "REC OFF";
    el.recDot.style.background = on ? "rgba(239,68,68,.95)" : "rgba(148,163,184,.85)";
    el.recDot.style.boxShadow = on ? "0 0 0 6px rgba(239,68,68,.20)" : "0 0 0 0 rgba(239,68,68,0)";

    const icon = el.btnRecord?.querySelector("i");
    if (icon) icon.className = on ? "fa-solid fa-stop" : "fa-solid fa-circle";
  }
  setRec(false);

  // ---------------- Permissions (cam/mic preview) ----------------
  async function enableCamMic() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
      state.camStream = stream;

      if (el.video) el.video.srcObject = stream;
      if (el.overlay) el.overlay.style.display = "none";

      const vTrack = stream.getVideoTracks()[0];
      const aTrack = stream.getAudioTracks()[0];
      if (vTrack) vTrack.enabled = true;
      if (aTrack) aTrack.enabled = true;

      state.camOn = !!vTrack;
      state.micOn = !!aTrack;

      updateCamIcon();
      updateMicIcon();
      return true;
    } catch (e) {
      console.error(e);
      alert("Camera/Mic permission is required.");
      return false;
    }
  }

  function updateCamIcon() {
    const icon = el.btnToggleCam?.querySelector("i");
    if (!icon) return;
    icon.className = state.camOn ? "fa-solid fa-video" : "fa-solid fa-video-slash";
  }

  function updateMicIcon() {
    const icon = el.btnToggleMic?.querySelector("i");
    if (!icon) return;
    icon.className = state.micOn ? "fa-solid fa-microphone" : "fa-solid fa-microphone-slash";
  }

  function toggleCam() {
    if (!state.camStream) return;
    const t = state.camStream.getVideoTracks()[0];
    if (!t) return;
    t.enabled = !t.enabled;
    state.camOn = t.enabled;

    if (el.overlay) el.overlay.style.display = state.camOn ? "none" : "flex";
    updateCamIcon();
  }

  function toggleMic() {
    if (!state.camStream) return;
    const t = state.camStream.getAudioTracks()[0];
    if (!t) return;
    t.enabled = !t.enabled;
    state.micOn = t.enabled;
    updateMicIcon();
  }

  // ---------------- Screen Recording (optional) ----------------
  async function startScreenRecording() {
    if (state.recOn) return;

    try {
      const screen = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: true });
      state.screenStream = screen;

      const mixed = new MediaStream();
      screen.getVideoTracks().forEach((t) => mixed.addTrack(t));
      screen.getAudioTracks().forEach((t) => mixed.addTrack(t));

      // mix mic from camStream if present
      if (state.camStream) {
        const mic = state.camStream.getAudioTracks()[0];
        if (mic) mixed.addTrack(mic);
      }

      state.recChunks = [];
      const recorder = new MediaRecorder(mixed, { mimeType: "video/webm" });
      state.screenRecorder = recorder;

      recorder.ondataavailable = (ev) => {
        if (ev.data && ev.data.size > 0) state.recChunks.push(ev.data);
      };

      recorder.onstop = () => {
        const blob = new Blob(state.recChunks, { type: "video/webm" });
        const url = URL.createObjectURL(blob);

        const a = document.createElement("a");
        a.href = url;
        a.download = `hirenext_interview_${Date.now()}.webm`;
        document.body.appendChild(a);
        a.click();
        a.remove();

        setTimeout(() => URL.revokeObjectURL(url), 2000);
      };

      recorder.start(1000);
      setRec(true);
    } catch (e) {
      console.error(e);
      alert("Screen recording failed (permission denied or unsupported).");
    }
  }

  function stopScreenRecording() {
    if (!state.recOn) return;

    try {
      if (state.screenRecorder && state.screenRecorder.state !== "inactive") state.screenRecorder.stop();
    } catch {}

    try {
      (state.screenStream?.getTracks() || []).forEach((t) => t.stop());
    } catch {}
    state.screenStream = null;

    setRec(false);
  }

  function toggleScreenRecording() {
    if (state.recOn) stopScreenRecording();
    else startScreenRecording();
  }

  // ---------------- Question helpers ----------------
  function curQuestion() {
    return state.questions[state.qIndex] || null;
  }

  function getQuestionId(q) {
    if (!q) return "";
    return String(q.id || q.question_id || q._id || "").trim();
  }

  // ---------------- Browser TTS ----------------
  function speak(text) {
    const msg = String(text || "");
    if (!msg.trim()) return;

    try {
      window.speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(msg);
      u.rate = 1.0;
      u.pitch = 1.0;
      window.speechSynthesis.speak(u);
    } catch (e) {
      console.error(e);
    }
  }

  function autoSpeakCurrentQuestion() {
    const q = curQuestion();
    if (!q) return;
    setTimeout(() => speak(q.question || ""), state.autoSpeakDelayMs);
  }

  function renderQuestion() {
    if (!hasOptionAI) return;

    const q = curQuestion();

    // ✅ finished all questions
    if (!q) {
      if (el.qMeta) el.qMeta.textContent = "All questions completed ✅";
      if (el.qText) el.qText.textContent = "Results will open in a popup.";
      setControlsEnabled({ record: false });

      setScoreLine("Interview completed ✅");
      setAiLoading(false);

      // Auto open results (best effort)
      openResultsOnce();
      return;
    }

    const total = state.questions.length || 0;
    if (el.qMeta) el.qMeta.textContent = `Question ${state.qIndex + 1}/${total}`;
    if (el.qText) el.qText.textContent = q.question || "Question";

    state.lastAnswerBlob = null;

    // reset record button icon
    if (el.btnRecAns) {
      el.btnRecAns.classList.remove("is-recording");
      const icon = el.btnRecAns.querySelector("i");
      if (icon) icon.className = "fa-solid fa-microphone";
    }

    setControlsEnabled({ record: true });
    setScoreLine("");
    setAiLoading(false);

    autoSpeakCurrentQuestion();
  }

  // ---------------- Audio Answer Recording ----------------
  function pickBestAudioMime() {
    const candidates = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/ogg"];
    for (const c of candidates) {
      if (window.MediaRecorder && MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(c)) return c;
    }
    return "";
  }

  async function ensureAnswerMic() {
    if (state.ansStream) return state.ansStream;
    state.ansStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    return state.ansStream;
  }

  async function startAnswerRecording() {
    if (state.ansRecOn) return;

    await ensureAnswerMic();
    state.ansChunks = [];
    state.lastAnswerBlob = null;

    const mimeType = pickBestAudioMime();
    let rec;
    try {
      rec = mimeType ? new MediaRecorder(state.ansStream, { mimeType }) : new MediaRecorder(state.ansStream);
    } catch (e) {
      console.error(e);
      alert("Recording is not supported in this browser.");
      return;
    }

    state.ansRecorder = rec;

    rec.ondataavailable = (ev) => {
      if (ev.data && ev.data.size > 0) state.ansChunks.push(ev.data);
    };

    rec.onstop = async () => {
      const type = mimeType || (state.ansChunks[0] && state.ansChunks[0].type) || "audio/webm";
      state.lastAnswerBlob = new Blob(state.ansChunks, { type });
      await submitAnswerAuto();
    };

    rec.start();
    state.ansRecOn = true;

    // recording UI
    if (el.btnRecAns) {
      el.btnRecAns.classList.add("is-recording");
      const icon = el.btnRecAns.querySelector("i");
      if (icon) icon.className = "fa-solid fa-stop";
    }

    setScoreLine("Recording…");
    setAiLoading(false);
    setControlsEnabled({ record: true });
  }

  function stopAnswerRecording() {
    if (!state.ansRecOn) return;
    state.ansRecOn = false;

    try {
      if (state.ansRecorder && state.ansRecorder.state !== "inactive") state.ansRecorder.stop();
    } catch {}

    setControlsEnabled({ record: false });
    setScoreLine("Processing…");
    setAiLoading(true);

    if (el.btnRecAns) {
      el.btnRecAns.classList.remove("is-recording");
      const icon = el.btnRecAns.querySelector("i");
      if (icon) icon.className = "fa-solid fa-microphone";
    }
  }

  async function toggleAnswerRecording() {
    try {
      if (!state.ansRecOn) await startAnswerRecording();
      else stopAnswerRecording();
    } catch (e) {
      console.error(e);
      alert("Mic permission is required for recording answers.");
    }
  }

  // ---------------- Submit Answer (AUTO) ----------------
  async function submitAnswerAuto() {
    const q = curQuestion();
    if (!q) return;
    if (state.submitting) return;

    if (!state.interviewId || !state.role) {
      alert("Missing interviewId/role in __INTERVIEW_AI_CTX__");
      setAiLoading(false);
      setControlsEnabled({ record: true });
      return;
    }

    if (!state.lastAnswerBlob) {
      alert("No audio captured. Please record again.");
      setAiLoading(false);
      setControlsEnabled({ record: true });
      return;
    }

    const questionId = getQuestionId(q);
    if (!questionId) {
      alert("Question id missing.");
      setAiLoading(false);
      setControlsEnabled({ record: true });
      return;
    }

    state.submitting = true;
    setAiLoading(true);
    setScoreLine("Scoring…");

    const fd = new FormData();
    fd.append("interview_id", state.interviewId);
    fd.append("role", state.role);
    fd.append("question_id", questionId);
    fd.append("audio", state.lastAnswerBlob, "answer.webm");

    let res, data;
    try {
      res = await fetch(state.submitUrl, { method: "POST", body: fd, credentials: "same-origin" });
      data = await res.json().catch(() => ({}));
    } catch (e) {
      console.error(e);
      alert("Network error while submitting answer.");
      state.submitting = false;
      setAiLoading(false);
      setControlsEnabled({ record: true });
      return;
    }

    state.submitting = false;

    if (!res.ok || !data.ok) {
      console.error(data);
      alert(data.error || "Submit failed.");
      setAiLoading(false);
      setControlsEnabled({ record: true });
      return;
    }

    setAiLoading(false);

    if (data.final_overall_0_10 !== undefined && data.final_overall_0_10 !== null) {
      setScoreLine(`Saved ✅ Overall: ${data.final_overall_0_10}/10`);
    } else {
      setScoreLine("Saved ✅");
    }

    const isLast = state.qIndex >= (state.questions.length - 1);
    if (isLast) {
      setTimeout(() => {
        state.qIndex += 1;
        renderQuestion(); // calls openResultsOnce()
      }, state.autoNextDelayMs);
      return;
    }

    setTimeout(() => nextQuestion(), state.autoNextDelayMs);
  }

  function nextQuestion() {
    state.qIndex += 1;
    renderQuestion();
  }

  // ---------------- Wiring: cam/mic ----------------
  el.btnToggleCam?.addEventListener("click", async () => {
    if (!state.camStream) {
      const ok = await enableCamMic();
      if (!ok) return;
      return;
    }
    toggleCam();
  });

  el.btnToggleMic?.addEventListener("click", async () => {
    if (!state.camStream) {
      const ok = await enableCamMic();
      if (!ok) return;
      return;
    }
    toggleMic();
  });

  el.btnRecord?.addEventListener("click", toggleScreenRecording);

  // ✅ End → Results popup
  el.btnEnd?.addEventListener("click", () => {
    if (!state.resultsUrl) return;
    state.resultsOpened = true;
    openCenteredPopup(state.resultsUrl, { fallbackToRedirect: true });
  });

  // ---------------- Start ----------------
  if (hasOptionAI) {
    if (!state.role) setScoreLine("⚠️ Role missing in page context.");
    else if (!state.questions.length) setScoreLine("⚠️ No questions for this role.");

    el.btnRecAns?.addEventListener("click", toggleAnswerRecording);
    renderQuestion();
  }
});