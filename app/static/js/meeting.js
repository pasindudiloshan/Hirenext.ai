/* static/js/meeting.js
   Meeting editor page
   - Loads interview via GET /interview/api/interview/<id>
   - Saves updates via POST /interview/api/interview/<id>/update
   - Cancels via POST /interview/api/interview/<id>/cancel
*/

document.addEventListener("DOMContentLoaded", () => {
  const id = (window.__MEETING__ && window.__MEETING__.interviewId) || "";

  const el = {
    statusPill: document.getElementById("statusPill"),
    metaLine: document.getElementById("metaLine"),
    alert: document.getElementById("formAlert"),

    form: document.getElementById("meetingForm"),
    btnSave: document.getElementById("btnSave"),
    btnReload: document.getElementById("btnReload"),
    btnCancel: document.getElementById("btnCancel"),

    // form fields
    title: document.getElementById("title"),
    type: document.getElementById("type"),
    date: document.getElementById("date"),
    time: document.getElementById("time"),
    duration: document.getElementById("duration"),
    status: document.getElementById("status"),
    meeting_link: document.getElementById("meeting_link"),
    notes: document.getElementById("notes"),

    // read only
    candName: document.getElementById("candName"),
    candEmail: document.getElementById("candEmail"),
    jobTitle: document.getElementById("jobTitle"),
    batchId: document.getElementById("batchId"),
    tz: document.getElementById("tz"),
    startTime: document.getElementById("startTime"),
    endTime: document.getElementById("endTime"),
  };

  if (!id || !el.form) return;

  function setAlert(type, msg) {
    if (!el.alert) return;
    el.alert.style.display = "block";
    el.alert.className = "mt-alert " + (type === "ok" ? "ok" : "err");
    el.alert.textContent = msg || "";
  }

  function clearAlert() {
    if (!el.alert) return;
    el.alert.style.display = "none";
    el.alert.textContent = "";
  }

  function setPill(status) {
    if (!el.statusPill) return;
    const st = (status || "SCHEDULED").toUpperCase();
    el.statusPill.textContent = st;
    el.statusPill.className = "mt-pill " + (
      st === "CANCELLED" ? "danger" :
      st === "COMPLETED" ? "success" :
      st === "CONFIRMED" ? "ok" :
      st === "NO_SHOW" ? "warn" :
      "default"
    );
  }

  function safeStr(x) { return (x === null || x === undefined) ? "" : String(x); }

  function timeFromLabelOrISO(interview) {
    // Prefer start_label "HH:MM"
    const lab = safeStr(interview.start_label || "");
    if (lab && /^\d{2}:\d{2}$/.test(lab)) return lab;

    // fallback: parse start_time ISO
    const iso = safeStr(interview.start_time || "");
    if (!iso) return "";
    const dt = new Date(iso);
    if (isNaN(dt.getTime())) return "";
    const hh = String(dt.getHours()).padStart(2, "0");
    const mm = String(dt.getMinutes()).padStart(2, "0");
    return `${hh}:${mm}`;
  }

  function fill(interview) {
    clearAlert();

    setPill(interview.status);

    if (el.metaLine) {
      el.metaLine.textContent = `Interview ID: ${safeStr(interview._id || id)}`;
    }

    // form fields
    el.title.value = safeStr(interview.title || "");
    el.type.value = safeStr(interview.type || "Interview");

    el.date.value = safeStr(interview.date || "");
    el.time.value = timeFromLabelOrISO(interview) || "10:00";

    // duration can be stored as duration_min
    const dur = interview.duration_min ?? interview.duration ?? 30;
    el.duration.value = String(Number(dur) || 30);

    el.status.value = safeStr(interview.status || "SCHEDULED");
    el.meeting_link.value = safeStr(interview.meeting_link || "");
    el.notes.value = safeStr(interview.notes || "");

    // read-only
    el.candName.textContent = safeStr(interview.candidate_name || "-");
    const email = safeStr(interview.candidate_email || "");
    el.candEmail.textContent = email || "-";
    el.candEmail.href = email ? `mailto:${email}` : "#";

    el.jobTitle.textContent = safeStr(interview.job_title || "-");
    el.batchId.textContent = safeStr(interview.batch_id || "-");
    el.tz.textContent = safeStr(interview.tz || "-");

    el.startTime.textContent = safeStr(interview.start_time || "-");
    el.endTime.textContent = safeStr(interview.end_time || "-");

    // disable save if cancelled
    const cancelled = (safeStr(interview.status || "").toUpperCase() === "CANCELLED");
    el.btnSave.disabled = cancelled;
    el.btnCancel.disabled = cancelled;
  }

  async function fetchInterview() {
    setAlert("ok", "Loading...");
    try {
      const res = await fetch(`/interview/api/interview/${encodeURIComponent(id)}`, { method: "GET" });
      const data = await res.json();
      if (!data.ok) throw new Error(data.error || "Failed to load");

      fill(data.interview || {});
      clearAlert();
    } catch (e) {
      setAlert("err", e.message || "Load failed");
    }
  }

  async function saveInterview(payload) {
    setAlert("ok", "Saving...");
    try {
      const res = await fetch(`/interview/api/interview/${encodeURIComponent(id)}/update`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload || {})
      });

      const data = await res.json();
      if (!data.ok) throw new Error(data.error || "Save failed");

      // Refresh view using returned interview if present, otherwise refetch
      if (data.interview) {
        fill(data.interview);
      } else {
        await fetchInterview();
      }
      setAlert("ok", "Saved ✅");
      setTimeout(clearAlert, 1200);
    } catch (e) {
      setAlert("err", e.message || "Save failed");
    }
  }

  async function cancelInterview() {
    const yes = window.confirm("Cancel this interview? This will mark it as CANCELLED.");
    if (!yes) return;

    setAlert("ok", "Cancelling...");
    try {
      const res = await fetch(`/interview/api/interview/${encodeURIComponent(id)}/cancel`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({})
      });

      const data = await res.json();
      if (!data.ok) throw new Error(data.error || "Cancel failed");

      if (data.interview) fill(data.interview);
      setAlert("ok", "Cancelled ✅");
      setTimeout(clearAlert, 1400);
    } catch (e) {
      setAlert("err", e.message || "Cancel failed");
    }
  }

  // Bind
  el.form.addEventListener("submit", (e) => {
    e.preventDefault();
    clearAlert();

    const date = el.date.value.trim();
    const time = el.time.value.trim();
    const duration = Number(el.duration.value || 30);

    if (!date || !time) {
      setAlert("err", "Date and Time are required.");
      return;
    }
    if (!Number.isFinite(duration) || duration < 5) {
      setAlert("err", "Duration must be at least 5 minutes.");
      return;
    }

    // payload uses controller allowed fields:
    const payload = {
      title: el.title.value.trim(),
      type: el.type.value,
      date,
      time,              // service will recompute labels + ISO using time+duration
      duration,          // maps to duration_min
      status: el.status.value,
      meeting_link: el.meeting_link.value.trim(),
      notes: el.notes.value.trim(),
    };

    saveInterview(payload);
  });

  el.btnReload?.addEventListener("click", fetchInterview);
  el.btnCancel?.addEventListener("click", cancelInterview);

  // Init load
  fetchInterview();
});