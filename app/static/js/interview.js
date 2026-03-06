/* static/js/interview.js — FULL UPDATED (MediaPipe Face Detection)
   ✅ Timer, cam/mic toggles, optional screen-record download
   ✅ Auto TTS on each question
   ✅ Record button toggles: start -> stop -> auto submit -> auto next
   ✅ AI panel shows loading dots while processing
   ✅ End interview opens results in centered popup
   ✅ FER upgraded with MediaPipe:
      - Detects face in frontend
      - Draws face box if overlay canvas exists
      - Crops face only before sending to backend
      - Updates emotion label + confidence
      - Sends emotion summary with answer submit
   ✅ Debug logs added so you can verify what is happening
*/

document.addEventListener("DOMContentLoaded", () => {
  const el = {
    timer: document.getElementById("ivTimer"),
    recDot: document.getElementById("ivRecDot"),
    recText: document.getElementById("ivRecText"),
    aiRing: document.getElementById("aiRing"),

    video: document.getElementById("candidateVideo"),
    overlay: document.getElementById("videoOverlay"),
    emotionOverlay: document.getElementById("emotionOverlay"),

    transcriptNow: document.getElementById("transcriptNow"),
    aiDots: document.getElementById("aiDots"),

    btnToggleCam: document.getElementById("btnToggleCam"),
    btnToggleMic: document.getElementById("btnToggleMic"),
    btnRecord: document.getElementById("btnRecord"),

    qMeta: document.getElementById("qMeta"),
    qText: document.getElementById("qText"),
    scoreLine: document.getElementById("scoreLine"),

    btnRecAns: document.getElementById("btnRecAns"),
    btnEnd: document.getElementById("btnEndInterview"),

    emotionBadge: document.getElementById("emotionBadge"),
    emotionText: document.getElementById("emotionText"),
    emotionConf: document.getElementById("emotionConf"),
  };

  const ctxAi = window.__INTERVIEW_AI_CTX__ || {};
  const ctxLegacy = window.__INTERVIEW_CTX__ || {};
  const hasOptionAI = !!(el.btnRecAns || el.qText);

  const state = {
    startedAt: Date.now(),
    timerT: null,

    camStream: null,
    camOn: false,
    micOn: false,

    recOn: false,
    screenStream: null,
    screenRecorder: null,
    recChunks: [],

    ansRecOn: false,
    ansStream: null,
    ansRecorder: null,
    ansChunks: [],
    lastAnswerBlob: null,

    submitting: false,

    questions: Array.isArray(ctxAi.questions) ? ctxAi.questions : [],
    role: String(ctxAi.role || ""),
    interviewId: String(ctxAi.interviewId || ctxAi.sessionId || ctxLegacy.interviewId || ""),
    submitUrl: String(ctxAi.submitUrl || "/interview-ai/submit-answer"),
    resultsUrl: String(ctxAi.resultsUrl || ""),
    qIndex: 0,

    autoSpeakDelayMs: 350,
    autoNextDelayMs: 350,

    resultsOpened: false,

    emotion: {
      enabled: true,
      debug: true,
      predictUrl: String((ctxAi.emotionPredictUrl || "") || "/emotion/predict"),
      intervalMs: Number(ctxAi.emotionIntervalMs || 2000),
      inFlight: false,
      t: null,

      lastLabel: "",
      lastConfidence: 0,
      counts: {},

      lastTs: 0,
      errors: 0,
      maxErrorsBeforeStop: 8,

      detector: null,
      detectorReady: false,
      lastFaceBox: null,
      paddingRatio: 0.18,
      fallbackToFullFrame: true,
      minDetectionScore: 0.5,
    },
  };

  function dlog(...args) {
    if (state.emotion.debug) console.log("[FER]", ...args);
  }

  function dwarn(...args) {
    if (state.emotion.debug) console.warn("[FER]", ...args);
  }

  function derror(...args) {
    if (state.emotion.debug) console.error("[FER]", ...args);
  }

  dlog("DOM loaded");
  dlog("emotionOverlay exists:", !!el.emotionOverlay);
  dlog("candidateVideo exists:", !!el.video);
  dlog("MediaPipe FaceDetection exists:", !!window.FaceDetection);

  const pad = (n) => String(n).padStart(2, "0");

  function fmtTime(ms) {
    const s = Math.max(0, Math.floor(ms / 1000));
    const mm = Math.floor(s / 60);
    const ss = s % 60;
    return `${pad(mm)}:${pad(ss)}`;
  }

  function clamp(v, min, max) {
    return Math.max(min, Math.min(max, v));
  }

  function startTimer() {
    if (state.timerT) return;
    state.startedAt = Date.now();
    state.timerT = setInterval(() => {
      if (el.timer) el.timer.textContent = fmtTime(Date.now() - state.startedAt);
    }, 500);
  }
  startTimer();

  function openCenteredPopupFallback(url, { fallbackToRedirect = true } = {}) {
    if (!url) return null;

    const w = 1180;
    const h = 760;
    const left = Math.floor((window.screen.width - w) / 2);
    const top = Math.floor((window.screen.height - h) / 2);

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

    if (!win || win.closed || typeof win.closed === "undefined") {
      if (fallbackToRedirect) window.location.href = url;
      return null;
    }

    win.focus();
    return win;
  }

  function openCenteredPopup(url, opts) {
    if (typeof window.openCenteredPopup === "function") {
      return window.openCenteredPopup(url);
    }
    return openCenteredPopupFallback(url, opts);
  }

  function openResultsOnce() {
    if (state.resultsOpened) return;
    if (!state.resultsUrl) return;

    state.resultsOpened = true;
    stopEmotionLoop();
    clearFaceOverlay();
    openCenteredPopup(state.resultsUrl, { fallbackToRedirect: true });
  }

  function setAiLoading(isLoading) {
    if (el.aiDots) el.aiDots.style.display = isLoading ? "flex" : "none";

    if (el.aiRing) {
      el.aiRing.style.boxShadow = isLoading
        ? "0 0 0 14px rgba(56,189,248,.16)"
        : "0 0 0 0 rgba(56,189,248,0)";
    }
  }
  setAiLoading(false);

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

      await initFaceDetector();

      dlog("Camera enabled");
      dlog("video:", el.video);
      dlog("overlay canvas:", el.emotionOverlay);

      startEmotionLoop();
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

    if (state.camOn) startEmotionLoop();
    else {
      stopEmotionLoop();
      clearFaceOverlay();
      hideEmotionUI();
    }
  }

  function toggleMic() {
    if (!state.camStream) return;
    const t = state.camStream.getAudioTracks()[0];
    if (!t) return;

    t.enabled = !t.enabled;
    state.micOn = t.enabled;
    updateMicIcon();
  }

  function hideEmotionUI() {
    if (el.emotionText) el.emotionText.textContent = "—";
    if (el.emotionConf) el.emotionConf.textContent = "";
    if (el.emotionBadge) el.emotionBadge.style.display = "none";
  }

  function setEmotionUI(label, conf, faceBox = null) {
    if (el.emotionText) el.emotionText.textContent = label ? String(label) : "—";
    if (el.emotionConf) el.emotionConf.textContent = conf ? `${Math.round(conf * 100)}%` : "";

    if (el.emotionBadge) {
      el.emotionBadge.style.display = label ? "flex" : "none";
      el.emotionBadge.style.opacity = label ? "1" : "0.75";

      if (faceBox && el.video) {
        positionEmotionBadge(faceBox);
      } else {
        el.emotionBadge.style.top = "14px";
        el.emotionBadge.style.left = "14px";
      }
    }
  }

  function positionEmotionBadge(faceBox) {
    if (!el.emotionBadge || !el.video || !faceBox) return;

    const vw = el.video.clientWidth || 1;
    const vh = el.video.clientHeight || 1;
    const sx = vw / (el.video.videoWidth || vw);
    const sy = vh / (el.video.videoHeight || vh);

    const badgeX = Math.max(10, Math.round(faceBox.x * sx));
    const badgeY = Math.max(10, Math.round(faceBox.y * sy) - 54);

    el.emotionBadge.style.left = `${badgeX}px`;
    el.emotionBadge.style.top = `${badgeY}px`;
  }

  async function initFaceDetector() {
    try {
      dlog("Initializing MediaPipe Face Detection...");

      if (!window.FaceDetection) {
        throw new Error("MediaPipe FaceDetection not loaded");
      }

      const detector = new window.FaceDetection({
        locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/face_detection/${file}`,
      });

      detector.setOptions({
        model: "short",
        minDetectionConfidence: state.emotion.minDetectionScore,
      });

      detector.onResults((results) => {
        state.emotion._latestResults = results || null;
      });

      state.emotion.detector = detector;
      state.emotion.detectorReady = true;

      dlog("MediaPipe Face Detection initialized");
      return true;
    } catch (e) {
      dwarn("MediaPipe init failed:", e);
      state.emotion.detector = null;
      state.emotion.detectorReady = false;
      return false;
    }
  }

  function getVideoFrameSize(videoEl) {
    const w = videoEl?.videoWidth || 0;
    const h = videoEl?.videoHeight || 0;
    return { w, h };
  }

  async function detectFaceBox(videoEl) {
    if (!videoEl) {
      dwarn("detectFaceBox: no video element");
      return null;
    }

    if (videoEl.readyState < 2) {
      dwarn("detectFaceBox: video not ready");
      return null;
    }

    const { w, h } = getVideoFrameSize(videoEl);
    if (!w || !h) {
      dwarn("detectFaceBox: invalid video size", w, h);
      return null;
    }

    if (!state.emotion.detectorReady || !state.emotion.detector) {
      dwarn("detectFaceBox: detector not ready");
      return null;
    }

    try {
      state.emotion._latestResults = null;

      await state.emotion.detector.send({ image: videoEl });

      const results = state.emotion._latestResults;
      const detections = results?.detections || [];

      dlog("MediaPipe detections:", detections);

      if (!Array.isArray(detections) || !detections.length) {
        dwarn("no face detected");
        return null;
      }

      let best = null;
      let bestArea = 0;

      for (const det of detections) {
        const box = det?.boundingBox;
        if (!box) continue;

        const bx = Number(box.xCenter || 0) - Number(box.width || 0) / 2;
        const by = Number(box.yCenter || 0) - Number(box.height || 0) / 2;
        const bw = Number(box.width || 0);
        const bh = Number(box.height || 0);

        if (bw <= 0 || bh <= 0) continue;

        const px = bx * w;
        const py = by * h;
        const pw = bw * w;
        const ph = bh * h;
        const area = pw * ph;

        if (area > bestArea) {
          bestArea = area;
          best = { x: px, y: py, width: pw, height: ph };
        }
      }

      if (!best) {
        dwarn("detections returned, but none usable");
        return null;
      }

      const padX = best.width * state.emotion.paddingRatio;
      const padY = best.height * state.emotion.paddingRatio;

      const x = clamp(Math.round(best.x - padX), 0, w - 1);
      const y = clamp(Math.round(best.y - padY), 0, h - 1);
      const right = clamp(Math.round(best.x + best.width + padX), 1, w);
      const bottom = clamp(Math.round(best.y + best.height + padY), 1, h);

      const out = {
        x,
        y,
        width: Math.max(1, right - x),
        height: Math.max(1, bottom - y),
      };

      state.emotion.lastFaceBox = out;
      dlog("face box:", out);
      return out;
    } catch (e) {
      dwarn("MediaPipe detection failed:", e);
      return null;
    }
  }

  function resizeOverlayCanvas() {
    if (!el.emotionOverlay || !el.video) return;

    const rect = el.video.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;

    el.emotionOverlay.width = Math.max(1, Math.round(rect.width * dpr));
    el.emotionOverlay.height = Math.max(1, Math.round(rect.height * dpr));
    el.emotionOverlay.style.width = `${Math.round(rect.width)}px`;
    el.emotionOverlay.style.height = `${Math.round(rect.height)}px`;

    dlog("overlay resized:", {
      width: el.emotionOverlay.width,
      height: el.emotionOverlay.height,
      cssWidth: el.emotionOverlay.style.width,
      cssHeight: el.emotionOverlay.style.height,
    });
  }

  function clearFaceOverlay() {
    if (!el.emotionOverlay) return;
    const ctx = el.emotionOverlay.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, el.emotionOverlay.width, el.emotionOverlay.height);
  }

  function drawFaceOverlay(faceBox, label = "", confidence = 0) {
    if (!el.emotionOverlay || !el.video || !faceBox) return;

    resizeOverlayCanvas();

    const ctx = el.emotionOverlay.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const vw = el.video.clientWidth || 1;
    const vh = el.video.clientHeight || 1;
    const sx = (vw * dpr) / (el.video.videoWidth || vw);
    const sy = (vh * dpr) / (el.video.videoHeight || vh);

    const x = faceBox.x * sx;
    const y = faceBox.y * sy;
    const w = faceBox.width * sx;
    const h = faceBox.height * sy;

    ctx.clearRect(0, 0, el.emotionOverlay.width, el.emotionOverlay.height);
    ctx.save();

    ctx.lineWidth = 3 * dpr;
    ctx.strokeStyle = "#22c55e";
    ctx.shadowColor = "rgba(34,197,94,.35)";
    ctx.shadowBlur = 16 * dpr;
    ctx.strokeRect(x, y, w, h);

    if (label) {
      const text = confidence
        ? `${String(label)} ${Math.round(confidence * 100)}%`
        : String(label);

      ctx.font = `${14 * dpr}px sans-serif`;
      const textW = ctx.measureText(text).width;
      const chipPadX = 10 * dpr;
      const chipH = 28 * dpr;
      const chipW = textW + chipPadX * 2;

      const chipX = x;
      const chipY = Math.max(6 * dpr, y - chipH - 8 * dpr);

      ctx.shadowBlur = 0;
      ctx.fillStyle = "rgba(15,23,42,.88)";
      roundRect(ctx, chipX, chipY, chipW, chipH, 10 * dpr);
      ctx.fill();

      ctx.strokeStyle = "rgba(250,204,21,.9)";
      ctx.lineWidth = 2 * dpr;
      roundRect(ctx, chipX, chipY, chipW, chipH, 10 * dpr);
      ctx.stroke();

      ctx.fillStyle = "#ffffff";
      ctx.textBaseline = "middle";
      ctx.fillText(text, chipX + chipPadX, chipY + chipH / 2);
    }

    ctx.restore();
  }

  function roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + w - r, y);
    ctx.quadraticCurveTo(x + w, y, x + w, y + r);
    ctx.lineTo(x + w, y + h - r);
    ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    ctx.lineTo(x + r, y + h);
    ctx.quadraticCurveTo(x, y + h, x, y + h - r);
    ctx.lineTo(x, y + r);
    ctx.quadraticCurveTo(x, y, x + r, y);
    ctx.closePath();
  }

  function captureVideoFrameBase64(videoEl) {
    if (!videoEl) return "";
    if (videoEl.readyState < 2) return "";

    const w = videoEl.videoWidth || 0;
    const h = videoEl.videoHeight || 0;
    if (!w || !h) return "";

    const canvas = document.createElement("canvas");
    canvas.width = w;
    canvas.height = h;

    const ctx = canvas.getContext("2d");
    if (!ctx) return "";

    ctx.drawImage(videoEl, 0, 0, w, h);
    return canvas.toDataURL("image/jpeg", 0.75);
  }

  function captureCroppedFaceBase64(videoEl, faceBox) {
    if (!videoEl || !faceBox) return "";

    const vw = videoEl.videoWidth || 0;
    const vh = videoEl.videoHeight || 0;
    if (!vw || !vh) return "";

    const sx = clamp(Math.round(faceBox.x), 0, vw - 1);
    const sy = clamp(Math.round(faceBox.y), 0, vh - 1);
    const sw = clamp(Math.round(faceBox.width), 1, vw - sx);
    const sh = clamp(Math.round(faceBox.height), 1, vh - sy);

    const canvas = document.createElement("canvas");
    canvas.width = sw;
    canvas.height = sh;

    const ctx = canvas.getContext("2d");
    if (!ctx) return "";

    ctx.drawImage(videoEl, sx, sy, sw, sh, 0, 0, sw, sh);
    return canvas.toDataURL("image/jpeg", 0.9);
  }

  async function captureBestEmotionImage(videoEl) {
    const faceBox = await detectFaceBox(videoEl);

    if (faceBox) {
      const cropped = captureCroppedFaceBase64(videoEl, faceBox);
      if (cropped) {
        dlog("capture source: face-crop", faceBox);
        return {
          image: cropped,
          faceBox,
          source: "face-crop",
        };
      }
      dwarn("face detected but crop failed");
    }

    if (state.emotion.fallbackToFullFrame) {
      const full = captureVideoFrameBase64(videoEl);
      if (full) {
        dwarn("capture source: full-frame");
        return {
          image: full,
          faceBox: null,
          source: "full-frame",
        };
      }
    }

    dwarn("capture source: none");
    return { image: "", faceBox: null, source: "none" };
  }

  async function predictEmotionOnce() {
    if (!state.emotion.enabled) return;
    if (!state.camOn) return;
    if (!el.video) return;
    if (state.emotion.inFlight) return;
    if (state.resultsOpened) return;

    state.emotion.lastTs = Date.now();
    state.emotion.inFlight = true;

    try {
      const capture = await captureBestEmotionImage(el.video);
      dlog("predictEmotionOnce capture:", capture.source, capture.faceBox);

      if (!capture.image) {
        clearFaceOverlay();
        return;
      }

      const res = await fetch(state.emotion.predictUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({
          image: capture.image,
          top_k: 3,
          debug: true,
        }),
      });

      const data = await res.json().catch(() => ({}));
      dlog("backend response:", data);
      dlog("backend image_source:", data.image_source);
      dlog("backend face_detected:", data.face_detected);
      dlog("backend face_box:", data.face_box);

      if (!res.ok || !data.ok) {
        state.emotion.errors += 1;
        dwarn("backend error:", data);
        if (state.emotion.errors >= state.emotion.maxErrorsBeforeStop) {
          stopEmotionLoop();
        }
        return;
      }

      const label = String(data.label || "");
      const confidence = Number(data.confidence || 0);

      state.emotion.lastLabel = label;
      state.emotion.lastConfidence = confidence;

      if (label) {
        state.emotion.counts[label] = (state.emotion.counts[label] || 0) + 1;
      }

      if (capture.faceBox) {
        drawFaceOverlay(capture.faceBox, label, confidence);
        setEmotionUI(label, confidence, capture.faceBox);
      } else if (data.face_box) {
        drawFaceOverlay(data.face_box, label, confidence);
        setEmotionUI(label, confidence, data.face_box);
      } else {
        clearFaceOverlay();
        setEmotionUI(label, confidence, null);
      }
    } catch (e) {
      derror("Emotion predict error:", e);
      state.emotion.errors += 1;
      if (state.emotion.errors >= state.emotion.maxErrorsBeforeStop) {
        stopEmotionLoop();
      }
    } finally {
      state.emotion.inFlight = false;
    }
  }

  function startEmotionLoop() {
    if (!state.emotion.enabled) return;
    if (!state.camOn) return;
    if (state.emotion.t) return;

    dlog("Starting emotion loop");

    if (el.emotionBadge || el.emotionText || el.emotionConf) {
      setEmotionUI(
        state.emotion.lastLabel || "",
        state.emotion.lastConfidence || 0,
        state.emotion.lastFaceBox
      );
    }

    state.emotion.t = setInterval(() => {
      predictEmotionOnce();
    }, state.emotion.intervalMs);

    setTimeout(() => {
      predictEmotionOnce();
    }, 600);
  }

  function stopEmotionLoop() {
    if (state.emotion.t) clearInterval(state.emotion.t);
    state.emotion.t = null;
    state.emotion.inFlight = false;
    dlog("Stopped emotion loop");
  }

  async function startScreenRecording() {
    if (state.recOn) return;

    try {
      const screen = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: true });
      state.screenStream = screen;

      const mixed = new MediaStream();
      screen.getVideoTracks().forEach((t) => mixed.addTrack(t));
      screen.getAudioTracks().forEach((t) => mixed.addTrack(t));

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
      if (state.screenRecorder && state.screenRecorder.state !== "inactive") {
        state.screenRecorder.stop();
      }
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

  function curQuestion() {
    return state.questions[state.qIndex] || null;
  }

  function getQuestionId(q) {
    if (!q) return "";
    return String(q.id || q.question_id || q._id || "").trim();
  }

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

    if (!q) {
      if (el.qMeta) el.qMeta.textContent = "All questions completed ✅";
      if (el.qText) el.qText.textContent = "Results will open in a popup.";
      setControlsEnabled({ record: false });

      setScoreLine("Interview completed ✅");
      setAiLoading(false);

      openResultsOnce();
      return;
    }

    const total = state.questions.length || 0;
    if (el.qMeta) el.qMeta.textContent = `Question ${state.qIndex + 1}/${total}`;
    if (el.qText) el.qText.textContent = q.question || "Question";

    state.lastAnswerBlob = null;

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

  function pickBestAudioMime() {
    const candidates = [
      "audio/webm;codecs=opus",
      "audio/webm",
      "audio/ogg;codecs=opus",
      "audio/ogg",
    ];

    for (const c of candidates) {
      if (window.MediaRecorder && MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(c)) {
        return c;
      }
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
      rec = mimeType
        ? new MediaRecorder(state.ansStream, { mimeType })
        : new MediaRecorder(state.ansStream);
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
      if (state.ansRecorder && state.ansRecorder.state !== "inactive") {
        state.ansRecorder.stop();
      }
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

    fd.append("emotion_label", String(state.emotion.lastLabel || ""));
    fd.append("emotion_confidence", String(state.emotion.lastConfidence || 0));
    fd.append("emotion_counts_json", JSON.stringify(state.emotion.counts || {}));

    let res, data;
    try {
      res = await fetch(state.submitUrl, {
        method: "POST",
        body: fd,
        credentials: "same-origin",
      });
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
        renderQuestion();
      }, state.autoNextDelayMs);
      return;
    }

    setTimeout(() => nextQuestion(), state.autoNextDelayMs);
  }

  function nextQuestion() {
    state.qIndex += 1;
    renderQuestion();
  }

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

  el.btnEnd?.addEventListener("click", () => {
    if (!state.resultsUrl) return;
    state.resultsOpened = true;
    stopEmotionLoop();
    clearFaceOverlay();
    openCenteredPopup(state.resultsUrl, { fallbackToRedirect: true });
  });

  window.addEventListener("resize", () => {
    resizeOverlayCanvas();
    if (state.emotion.lastFaceBox && state.emotion.lastLabel) {
      drawFaceOverlay(
        state.emotion.lastFaceBox,
        state.emotion.lastLabel,
        state.emotion.lastConfidence
      );
      positionEmotionBadge(state.emotion.lastFaceBox);
    }
  });

  el.video?.addEventListener("loadedmetadata", () => {
    dlog("video metadata loaded", {
      videoWidth: el.video.videoWidth,
      videoHeight: el.video.videoHeight,
      clientWidth: el.video.clientWidth,
      clientHeight: el.video.clientHeight,
    });
    resizeOverlayCanvas();
  });

  window.__FER_DRAW_TEST__ = function () {
    if (!el.emotionOverlay) {
      console.warn("No emotionOverlay canvas found");
      return;
    }
    resizeOverlayCanvas();
    const ctx = el.emotionOverlay.getContext("2d");
    if (!ctx) {
      console.warn("No canvas context");
      return;
    }
    ctx.clearRect(0, 0, el.emotionOverlay.width, el.emotionOverlay.height);
    ctx.strokeStyle = "red";
    ctx.lineWidth = 4;
    ctx.strokeRect(40, 40, 220, 220);
    console.log("Red test box drawn");
  };

  if (hasOptionAI) {
    if (!state.role) setScoreLine("⚠️ Role missing in page context.");
    else if (!state.questions.length) setScoreLine("⚠️ No questions for this role.");

    el.btnRecAns?.addEventListener("click", toggleAnswerRecording);
    renderQuestion();
  }
});