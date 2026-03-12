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

  function toast(icon, title) {
    return Swal.fire({
      toast: true,
      position: "top-end",
      icon,
      title,
      showConfirmButton: false,
      timer: 1800,
      timerProgressBar: true
    });
  }

  function showSuccess(title, text = "") {
    return Swal.fire({
      icon: "success",
      title,
      text,
      confirmButtonColor: "#16a34a"
    });
  }

  function showError(title, text = "") {
    return Swal.fire({
      icon: "error",
      title,
      text,
      confirmButtonColor: "#dc2626"
    });
  }

  function showWarning(title, text = "") {
    return Swal.fire({
      icon: "warning",
      title,
      text,
      confirmButtonColor: "#2563eb"
    });
  }

  function showLoading(title = "Please wait...") {
    Swal.fire({
      title,
      text: "Processing request...",
      allowOutsideClick: false,
      allowEscapeKey: false,
      didOpen: () => {
        Swal.showLoading();
      }
    });
  }

  function closeLoading() {
    Swal.close();
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

  function safeStr(x) {
    return (x === null || x === undefined) ? "" : String(x);
  }

  function timeFromLabelOrISO(interview) {
    const lab = safeStr(interview.start_label || "");
    if (lab && /^\d{2}:\d{2}$/.test(lab)) return lab;

    const iso = safeStr(interview.start_time || "");
    if (!iso) return "";

    const dt = new Date(iso);
    if (isNaN(dt.getTime())) return "";

    const hh = String(dt.getHours()).padStart(2, "0");
    const mm = String(dt.getMinutes()).padStart(2, "0");
    return `${hh}:${mm}`;
  }

  function fill(interview) {
    setPill(interview.status);

    if (el.metaLine) {
      el.metaLine.textContent = `Interview ID: ${safeStr(interview._id || id)}`;
    }

    // form fields
    el.title.value = safeStr(interview.title || "");
    el.type.value = safeStr(interview.type || "Interview");
    el.date.value = safeStr(interview.date || "");
    el.time.value = timeFromLabelOrISO(interview) || "10:00";

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

    const cancelled = safeStr(interview.status || "").toUpperCase() === "CANCELLED";
    el.btnSave.disabled = cancelled;
    el.btnCancel.disabled = cancelled;
  }

  async function fetchInterview(showNotice = false) {
    showLoading("Loading interview...");

    try {
      const res = await fetch(`/interview/api/interview/${encodeURIComponent(id)}`, {
        method: "GET"
      });

      const data = await res.json();
      if (!data.ok) throw new Error(data.error || "Failed to load interview.");

      fill(data.interview || {});
      closeLoading();

      if (showNotice) {
        toast("success", "Interview reloaded");
      }
    } catch (e) {
      closeLoading();
      showError("Load Failed", e.message || "Unable to load interview details.");
    }
  }

  async function saveInterview(payload) {
    showLoading("Saving changes...");

    try {
      const res = await fetch(`/interview/api/interview/${encodeURIComponent(id)}/update`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload || {})
      });

      const data = await res.json();
      if (!data.ok) throw new Error(data.error || "Save failed.");

      if (data.interview) {
        fill(data.interview);
      } else {
        await fetchInterview(false);
      }

      closeLoading();
      toast("success", "Interview updated successfully");
    } catch (e) {
      closeLoading();
      showError("Save Failed", e.message || "Unable to save interview changes.");
    }
  }

  async function cancelInterview() {
    const result = await Swal.fire({
      icon: "warning",
      title: "Cancel Interview?",
      text: "This will mark the interview as CANCELLED.",
      showCancelButton: true,
      confirmButtonColor: "#dc2626",
      cancelButtonColor: "#6b7280",
      confirmButtonText: "Yes, cancel it",
      cancelButtonText: "Keep it"
    });

    if (!result.isConfirmed) return;

    showLoading("Cancelling interview...");

    try {
      const res = await fetch(`/interview/api/interview/${encodeURIComponent(id)}/cancel`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({})
      });

      const data = await res.json();
      if (!data.ok) throw new Error(data.error || "Cancel failed.");

      if (data.interview) fill(data.interview);

      closeLoading();
      await showSuccess("Interview Cancelled", "The interview has been marked as cancelled.");
    } catch (e) {
      closeLoading();
      showError("Cancel Failed", e.message || "Unable to cancel this interview.");
    }
  }

  el.form.addEventListener("submit", (e) => {
    e.preventDefault();

    const date = el.date.value.trim();
    const time = el.time.value.trim();
    const duration = Number(el.duration.value || 30);

    if (!date || !time) {
      showWarning("Missing Required Fields", "Date and time are required.");
      return;
    }

    if (!Number.isFinite(duration) || duration < 5) {
      showWarning("Invalid Duration", "Duration must be at least 5 minutes.");
      return;
    }

    const payload = {
      title: el.title.value.trim(),
      type: el.type.value,
      date,
      time,
      duration,
      status: el.status.value,
      meeting_link: el.meeting_link.value.trim(),
      notes: el.notes.value.trim(),
    };

    saveInterview(payload);
  });

  el.btnReload?.addEventListener("click", () => fetchInterview(true));
  el.btnCancel?.addEventListener("click", cancelInterview);

  fetchInterview(false);
});