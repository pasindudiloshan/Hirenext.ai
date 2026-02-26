/* static/js/interview_schedule.js
   Cleaned + aligned with backend.

   Fixes:
   - Uses GET /interview/api/batch_interviews (matches Flask).
   - Uses existing Meeting Modal from schedule.html (no duplicate DOM / no injected CSS).
   - Meeting Link button no longer reloads day slots (prevents wiping UI state).
   - ✅ UPDATED: "Send Emails" opens mail.html popup (small window) instead of POST /send_invites.
*/

(function () {
  const ctx = window.__SCHEDULE_CTX__ || {};
  const activeBatch = ctx.activeBatch || {};
  const allCandidates = Array.isArray(ctx.shortlistedCandidates) ? ctx.shortlistedCandidates : [];
  const initialMeetingLink = ctx.meetingLink || "";
  const initialSelectedDateISO = ctx.selectedDate || "";

  const el = {
    grid: document.getElementById("calendarGrid"),
    monthLabel: document.getElementById("calMonth"),
    btnPrevMonth: document.getElementById("calPrev"),
    btnNextMonth: document.getElementById("calNext"),

    slotsList: document.getElementById("slotsList"),
    slotsDayLabel: document.getElementById("slotsDayLabel"),
    btnDayPrev: document.getElementById("dayPrev"),
    btnDayNext: document.getElementById("dayNext"),

    tzSelect: document.getElementById("tzSelect"),
    durationSelect: document.getElementById("durationSelect"),

    meetingLinkBtn: document.getElementById("meetingLinkBtn"),
    confirmSlotsBtn: document.getElementById("confirmSlotsBtn"),
    sendEmailsBtn: document.getElementById("sendEmailsBtn"),

    totalShortlisted: document.getElementById("totalShortlisted"),
    activeVacancyName: document.getElementById("activeVacancyName"),

    // existing modal in schedule.html
    meetingModal: document.getElementById("hnMeetingModal"),
    mmMeta: document.getElementById("hnMmMeta"),
    mmTable: document.getElementById("hnMmTable"),
    mmCopyAll: document.getElementById("hnMmCopyAll"),
  };

  const state = {
    viewDate: null,
    selectedDate: null,
    selectedSlotKeys: new Set(),
    daySlots: [],
    bookedSet: new Set(),
    meetingLink: initialMeetingLink || "",
    planned: [],

    scheduledCandidateIds: new Set(),
    remainingCandidates: [],
    lastDayInterviews: [],
  };

  const pad = (n) => String(n).padStart(2, "0");

  function getActiveBatchId() {
    return activeBatch?._id || activeBatch?.id || activeBatch?.batch_id || "";
  }

  function toISODate(d) {
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  }

  function parseISODate(iso) {
    if (!iso || typeof iso !== "string") return null;
    const [y, m, d] = iso.split("-").map(Number);
    if (!y || !m || !d) return null;
    return new Date(y, m - 1, d, 0, 0, 0, 0);
  }

  function isWeekday(d) {
    const day = d.getDay();
    return day >= 1 && day <= 5;
  }

  function addDays(d, n) {
    const x = new Date(d);
    x.setDate(x.getDate() + n);
    return x;
  }

  function fmtMonthYear(d) {
    return d.toLocaleDateString([], { month: "long", year: "numeric" });
  }

  function fmtDayLabel(d) {
    return d.toLocaleDateString([], { day: "2-digit", month: "short", year: "numeric" });
  }

  function mins(hhmm) {
    const [h, m] = String(hhmm).split(":").map(Number);
    return (h || 0) * 60 + (m || 0);
  }

  function slotKey(start, end) {
    return `${start}-${end}`;
  }

  function uuidToken() {
    try {
      return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
        const r = crypto.getRandomValues(new Uint8Array(1))[0] & 15;
        const v = c === "x" ? r : (r & 0x3) | 0x8;
        return v.toString(16);
      });
    } catch {
      return `rnd-${Math.random().toString(16).slice(2)}-${Date.now()}`;
    }
  }

  function setMeetingLink(link) {
    state.meetingLink = link || "";
  }

  function toast(msg, type = "info") {
    const t = document.createElement("div");
    t.textContent = msg;

    const bg =
      type === "ok" ? "rgba(34,197,94,.95)" :
      type === "warn" ? "rgba(245,158,11,.95)" :
      type === "err" ? "rgba(239,68,68,.95)" :
      "rgba(27,108,255,.95)";

    Object.assign(t.style, {
      position: "fixed",
      top: "86px",
      right: "18px",
      zIndex: 9999,
      background: bg,
      color: "#fff",
      padding: "10px 12px",
      borderRadius: "12px",
      boxShadow: "0 16px 32px rgba(0,0,0,.18)",
      fontWeight: "800",
      fontSize: "13px",
      maxWidth: "340px",
      transition: "opacity .25s ease, transform .25s ease",
    });

    document.body.appendChild(t);
    setTimeout(() => { t.style.opacity = "0"; t.style.transform = "translateY(-4px)"; }, 2200);
    setTimeout(() => t.remove(), 2600);
  }

  async function safeJSON(res) {
    try { return await res.json(); } catch { return {}; }
  }

  async function getJSON(url) {
    const res = await fetch(url, { credentials: "same-origin" });
    const data = await safeJSON(res);
    if (!res.ok) throw new Error(data.error || data.message || `GET failed (${res.status})`);
    return data;
  }

  async function postJSON(url, body) {
    const res = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await safeJSON(res);
    if (!res.ok) throw new Error(data.error || data.message || `POST failed (${res.status})`);
    return data;
  }

  function escapeHtml(s) {
    return String(s ?? "").replace(/[&<>"']/g, (m) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    }[m]));
  }

  // ---- Calendar Rendering ----
  function renderCalendar() {
    if (!el.grid || !el.monthLabel) return;

    const d = state.viewDate;
    const year = d.getFullYear();
    const month = d.getMonth();

    el.monthLabel.textContent = fmtMonthYear(d);

    const first = new Date(year, month, 1);
    const firstWeekday = first.getDay();
    const last = new Date(year, month + 1, 0);
    const daysInMonth = last.getDate();

    const prevLast = new Date(year, month, 0);
    const prevDays = prevLast.getDate();

    const cells = [];
    for (let i = 0; i < 42; i++) {
      const dayNum = i - firstWeekday + 1;
      let cellDate;
      let inMonth = true;

      if (dayNum < 1) {
        cellDate = new Date(year, month - 1, prevDays + dayNum);
        inMonth = false;
      } else if (dayNum > daysInMonth) {
        cellDate = new Date(year, month + 1, dayNum - daysInMonth);
        inMonth = false;
      } else {
        cellDate = new Date(year, month, dayNum);
      }

      const iso = toISODate(cellDate);
      const isSelected = state.selectedDate && toISODate(state.selectedDate) === iso;
      const isToday = toISODate(new Date()) === iso;
      const weekdayOK = isWeekday(cellDate);

      cells.push({ cellDate, inMonth, isSelected, isToday, weekdayOK });
    }

    el.grid.innerHTML = cells.map((c) => {
      const classes = [
        "day",
        c.inMonth ? "" : "muted",
        c.isSelected ? "selected" : "",
        c.isToday ? "today" : "",
        c.weekdayOK ? "" : "disabled",
      ].filter(Boolean).join(" ");

      const label = c.cellDate.getDate();
      const iso = toISODate(c.cellDate);

      return `
        <button class="${classes}" type="button" data-iso="${iso}"
          ${c.weekdayOK ? "" : "disabled"} aria-label="${iso}">
          ${label}
        </button>
      `;
    }).join("");

    el.grid.querySelectorAll(".day").forEach((btn) => {
      btn.addEventListener("click", () => {
        const iso = btn.getAttribute("data-iso");
        const dd = parseISODate(iso);
        if (!dd || !isWeekday(dd)) return;
        selectDate(dd, { keepMonth: true });
      });
    });
  }

  function moveMonth(delta) {
    const d = new Date(state.viewDate);
    d.setMonth(d.getMonth() + delta, 1);
    state.viewDate = d;
    renderCalendar();
  }

  function toAmPm(hhmmStr) {
    const [h, m] = String(hhmmStr).split(":").map(Number);
    const ampm = h >= 12 ? "PM" : "AM";
    const hh = ((h + 11) % 12) + 1;
    return `${pad(hh)}:${pad(m)} ${ampm}`;
  }

  async function refreshBatchScheduledCandidates() {
    const batchId = getActiveBatchId();
    if (!batchId) {
      state.scheduledCandidateIds = new Set();
      state.remainingCandidates = [...allCandidates];
      return;
    }

    try {
      // ✅ fixed endpoint
      const data = await getJSON(`/interview/api/batch_interviews?batch_id=${encodeURIComponent(batchId)}`);
      const arr = Array.isArray(data.scheduled_candidate_ids) ? data.scheduled_candidate_ids : [];
      state.scheduledCandidateIds = new Set(arr.map((x) => String(x)));
    } catch {
      state.scheduledCandidateIds = new Set();
    }

    state.remainingCandidates = allCandidates.filter((c) => {
      const cid = getCandidateId(c);
      if (!cid) return true;
      return !state.scheduledCandidateIds.has(String(cid));
    });
  }

  async function loadDaySlots() {
    if (!state.selectedDate) return;

    const batchId = getActiveBatchId();
    if (!batchId) {
      state.daySlots = [];
      state.bookedSet = new Set();
      state.selectedSlotKeys.clear();
      state.lastDayInterviews = [];
      if (el.slotsList) el.slotsList.innerHTML = `<div class="slot-skeleton">Select a job vacancy (batch) first</div>`;
      toast("Select a vacancy batch first.", "warn");
      return;
    }

    await refreshBatchScheduledCandidates();

    const dateISO = toISODate(state.selectedDate);
    const tz = el.tzSelect?.value || "Asia/Colombo";
    const duration = Number(el.durationSelect?.value || 10);

    state.selectedSlotKeys.clear();
    state.daySlots = [];
    state.bookedSet = new Set();
    state.lastDayInterviews = [];

    const url =
      `/interview/api/day_slots?batch_id=${encodeURIComponent(batchId)}` +
      `&date=${encodeURIComponent(dateISO)}` +
      `&duration=${encodeURIComponent(duration)}` +
      `&tz=${encodeURIComponent(tz)}`;

    try {
      const data = await getJSON(url);

      if (Array.isArray(data.booked)) data.booked.forEach((k) => state.bookedSet.add(String(k)));
      if (Array.isArray(data.interviews)) state.lastDayInterviews = data.interviews;

      if (Array.isArray(data.slots) && data.slots.length) {
        state.daySlots = data.slots.map((s) => {
          if (s.is_break) return { is_break: true, label: s.label || "Break" };
          const key = slotKey(s.start, s.end);
          return {
            start: s.start,
            end: s.end,
            label: s.label || `${toAmPm(s.start)}  -  ${toAmPm(s.end)}`,
            is_break: false,
            is_booked: Boolean(s.is_booked) || state.bookedSet.has(key),
          };
        });
      } else {
        state.daySlots = [];
      }

      if (data.meeting_link) setMeetingLink(data.meeting_link);
    } catch (e) {
      state.daySlots = [];
      toast(e.message || "Failed to load day slots.", "err");
    }

    renderSlots();
  }

  function renderSlots() {
    if (!el.slotsList || !el.slotsDayLabel || !state.selectedDate) return;

    el.slotsDayLabel.textContent = fmtDayLabel(state.selectedDate);

    const maxPick = Math.max(0, state.remainingCandidates.length);
    const pickedCount = state.selectedSlotKeys.size;

    const html = [];
    for (const s of state.daySlots) {
      if (s.is_break) {
        html.push(`
          <div class="slot-item break">
            <div class="break-box">
              <div class="break-time">${escapeHtml(s.label || "Break")}</div>
              <div class="break-text">Break</div>
            </div>
          </div>
        `);
        continue;
      }

      const key = slotKey(s.start, s.end);
      const booked = !!s.is_booked;
      const checked = state.selectedSlotKeys.has(key);
      const lockMore = !checked && pickedCount >= maxPick;
      const dotClass = booked ? "dot-gray" : checked ? "dot-orange" : "dot-green";

      html.push(`
        <label class="slot-item ${booked ? "booked" : ""}">
          <input type="checkbox" name="slotPick" value="${key}"
            ${booked ? "disabled" : ""} ${lockMore ? "disabled" : ""} ${checked ? "checked" : ""}>
          <span class="slot-dot ${dotClass}"></span>
          <span class="slot-time">${escapeHtml(s.label)}</span>
        </label>
      `);
    }

    el.slotsList.innerHTML = html.join("");

    el.slotsList.querySelectorAll('input[name="slotPick"]').forEach((chk) => {
      chk.addEventListener("change", () => {
        const key = chk.value;

        if (chk.checked) {
          if (state.selectedSlotKeys.size >= maxPick) {
            chk.checked = false;
            toast(`You can select only ${maxPick} slot(s) (remaining candidates).`, "warn");
            return;
          }
          state.selectedSlotKeys.add(key);
        } else {
          state.selectedSlotKeys.delete(key);
        }
        renderSlots();
      });
    });
  }

  function selectDate(dateObj, { keepMonth = false } = {}) {
    if (!dateObj || !isWeekday(dateObj)) {
      toast("Weekdays only (Mon–Fri).", "warn");
      return;
    }

    state.selectedDate = new Date(dateObj.getFullYear(), dateObj.getMonth(), dateObj.getDate());

    // ✅ keep window.__SCHEDULE_CTX__.selectedDate updated for popup usage
    try {
      window.__SCHEDULE_CTX__ = window.__SCHEDULE_CTX__ || {};
      window.__SCHEDULE_CTX__.selectedDate = toISODate(state.selectedDate);
    } catch {}

    if (!keepMonth) {
      state.viewDate = new Date(state.selectedDate.getFullYear(), state.selectedDate.getMonth(), 1);
    }

    renderCalendar();
    loadDaySlots();
  }

  function jumpToNextWeekday(delta) {
    if (!state.selectedDate) return;
    let d = addDays(state.selectedDate, delta);
    while (!isWeekday(d)) d = addDays(d, delta);
    selectDate(d, { keepMonth: false });
  }

  function regenerateMeetingLink() {
    const batchName = (activeBatch?.job_title || "Interview").replace(/\s+/g, "-");
    const dateISO = state.selectedDate ? toISODate(state.selectedDate) : "date";
    const token = uuidToken().slice(0, 8);
    const link = `https://meet.hirenext.ai/${encodeURIComponent(batchName)}-${dateISO}-${token}`;
    setMeetingLink(link);

    // ✅ keep ctx meetingLink updated for popup usage
    try {
      window.__SCHEDULE_CTX__ = window.__SCHEDULE_CTX__ || {};
      window.__SCHEDULE_CTX__.meetingLink = link;
    } catch {}

    return link;
  }

  function slotToPayload(startHHMM, endHHMM) {
    const d = state.selectedDate;
    const dateISO = toISODate(d);
    return {
      start_label: startHHMM,
      end_label: endHHMM,
      start_time: `${dateISO}T${startHHMM}:00`,
      end_time: `${dateISO}T${endHHMM}:00`,
    };
  }

  function getCandidateName(c) {
    return c?.name || c?.candidate_name || c?.full_name || c?.candidate || "Candidate";
  }
  function getCandidateEmail(c) {
    return c?.email || c?.candidate_email || c?.mail || "";
  }
  function getCandidateId(c) {
    return c?._id || c?.id || c?.candidate_id || null;
  }

  // ---- Meeting Modal (use existing HTML modal) ----
  function openMeetingModal(rows) {
    if (!el.meetingModal || !el.mmMeta || !el.mmTable || !el.mmCopyAll) {
      toast("Meeting modal not found in HTML.", "err");
      return;
    }

    const dateISO = state.selectedDate ? toISODate(state.selectedDate) : "";
    const batchName = activeBatch?.job_title || "—";

    el.mmMeta.textContent = `Vacancy: ${batchName} • Date: ${dateISO} • Total: ${rows.length}`;

    el.mmTable.innerHTML = rows.map((r, idx) => {
      const safeName = escapeHtml(r.candidate_name || `Candidate ${idx + 1}`);
      const safeTime = escapeHtml(r.slot_label || "");
      const safeLink = escapeHtml(r.meeting_link || "");
      const copyVal = escapeHtml(r.copy_text || r.meeting_link || "");
      return `
        <div class="hn-mm-row">
          <div><strong>${safeName}</strong></div>
          <div><span class="hn-mm-pill">${safeTime}</span></div>
          <div class="hn-mm-link" title="${safeLink}">${safeLink}</div>
          <button class="hn-mm-copy" type="button" data-copy="${copyVal}">Copy</button>
        </div>
      `;
    }).join("");

    el.mmTable.querySelectorAll("[data-copy]").forEach((btn) => {
      btn.addEventListener("click", () => copyText(btn.getAttribute("data-copy") || ""));
    });

    el.mmCopyAll.onclick = () => {
      const all = rows.map((r) => r.copy_text || `${r.candidate_name} | ${r.slot_label} | ${r.meeting_link}`).join("\n");
      copyText(all);
    };

    el.meetingModal.classList.add("open");
    el.meetingModal.setAttribute("aria-hidden", "false");
  }

  async function copyText(text) {
    try {
      await navigator.clipboard.writeText(text);
      toast("Copied!", "ok");
      return true;
    } catch {
      toast("Copy failed.", "err");
      return false;
    }
  }

  function slotLabelForKey(key) {
    const [start, end] = key.split("-");
    const found = state.daySlots.find((s) => !s.is_break && s.start === start && s.end === end);
    return found?.label || `${toAmPm(start)}  -  ${toAmPm(end)}`;
  }

  async function onMeetingLinkClick() {
    if (!state.selectedDate) return toast("Select a weekday date first.", "warn");

    const batchId = getActiveBatchId();
    if (!batchId) return toast("Select a vacancy batch first.", "warn");

    const selectedKeys = Array.from(state.selectedSlotKeys).sort((a, b) => mins(a.split("-")[0]) - mins(b.split("-")[0]));

    // if slots selected -> preview for remaining candidates
    if (selectedKeys.length > 0) {
      await refreshBatchScheduledCandidates();

      if (state.remainingCandidates.length === 0) return toast("All candidates already scheduled in this batch.", "warn");
      if (selectedKeys.length > state.remainingCandidates.length) {
        return toast(`Too many slots selected. Remaining candidates: ${state.remainingCandidates.length}`, "warn");
      }

      const link = regenerateMeetingLink();

      const rows = state.remainingCandidates.slice(0, selectedKeys.length).map((c, idx) => {
        const key = selectedKeys[idx];
        const label = slotLabelForKey(key);
        const name = getCandidateName(c);
        return {
          candidate_name: name,
          slot_label: label,
          meeting_link: link,
          copy_text: `${name} | ${label} | ${link}`,
        };
      });

      openMeetingModal(rows);
      return;
    }

    // if NO slots selected -> show confirmed interviews already fetched for the date
    const interviews = Array.isArray(state.lastDayInterviews) ? state.lastDayInterviews : [];
    if (!interviews.length) {
      const link = state.meetingLink || regenerateMeetingLink();
      toast("No confirmed interviews on this date yet.", "warn");
      console.log("Meeting Link:", link);
      return;
    }

    const sorted = interviews.slice().sort((a, b) => mins(a.start_label || "00:00") - mins(b.start_label || "00:00"));
    const rows = sorted.map((it) => {
      const name = it.candidate_name || "Candidate";
      const st = it.start_label || "";
      const en = it.end_label || "";
      const label = (st && en) ? `${toAmPm(st)}  -  ${toAmPm(en)}` : (st ? toAmPm(st) : "—");
      const link = it.meeting_link || state.meetingLink || "";
      return {
        candidate_name: name,
        slot_label: label,
        meeting_link: link,
        copy_text: `${name} | ${label} | ${link}`,
      };
    });

    openMeetingModal(rows);
  }

  async function confirmSlots() {
    const batchId = getActiveBatchId();
    if (!batchId) return toast("No active batch selected.", "warn");
    if (!state.selectedDate) return toast("Select a weekday date.", "warn");
    if (!allCandidates.length) return toast("No shortlisted candidates.", "warn");

    await refreshBatchScheduledCandidates();
    if (state.remainingCandidates.length === 0) return toast("All candidates already scheduled for this batch.", "warn");

    const dateISO = toISODate(state.selectedDate);
    const tz = el.tzSelect?.value || "Asia/Colombo";
    const duration = Number(el.durationSelect?.value || 10);

    const selectedKeys = Array.from(state.selectedSlotKeys).sort((a, b) => mins(a.split("-")[0]) - mins(b.split("-")[0]));
    if (selectedKeys.length === 0) return toast("Select at least 1 slot to confirm.", "warn");
    if (selectedKeys.length > state.remainingCandidates.length) {
      return toast(`You selected ${selectedKeys.length} slots but only ${state.remainingCandidates.length} candidates remain.`, "warn");
    }

    const meetingLink = state.meetingLink || regenerateMeetingLink();
    const chosenCandidates = state.remainingCandidates.slice(0, selectedKeys.length);

    const plan = chosenCandidates.map((c, idx) => {
      const key = selectedKeys[idx];
      const [start, end] = key.split("-");
      const payload = slotToPayload(start, end);

      return {
        candidate_name: getCandidateName(c),
        candidate_email: getCandidateEmail(c),
        candidate_id: getCandidateId(c),
        ...payload,
        meeting_link: meetingLink,
      };
    });

    state.planned = plan;

    try {
      if (el.confirmSlotsBtn) el.confirmSlotsBtn.disabled = true;
      toast("Saving schedule…", "info");

      const out = await postJSON("/interview/api/schedule", {
        batch_id: batchId,
        date: dateISO,
        tz,
        duration,
        meeting_link: meetingLink,
        interviews: plan,
      });

      toast(out.message || "Slots confirmed & saved.", "ok");

      plan.forEach((p) => { if (p.candidate_id) state.scheduledCandidateIds.add(String(p.candidate_id)); });
      plan.forEach((p) => state.bookedSet.add(`${p.start_label}-${p.end_label}`));

      state.selectedSlotKeys.clear();

      await refreshBatchScheduledCandidates();
      await loadDaySlots();
      renderSlots();
    } catch (e) {
      toast(e.message || "Failed to save schedule.", "err");
    } finally {
      if (el.confirmSlotsBtn) el.confirmSlotsBtn.disabled = false;
    }
  }

  // ✅ UPDATED: open mail.html popup
  function sendEmails() {
    if (!state.selectedDate) return toast("Select a date first.", "warn");

    const dateISO = toISODate(state.selectedDate);
    const link = (state.meetingLink || "").trim();

    const url =
      `/interview/mail?date=${encodeURIComponent(dateISO)}&link=${encodeURIComponent(link)}`;

    window.open(
      url,
      "HireNextMailPopup",
      "width=520,height=420,left=260,top=140,resizable=yes,scrollbars=yes"
    );
  }

  function bindModalClose() {
    if (!el.meetingModal) return;
    el.meetingModal.addEventListener("click", (e) => {
      const t = e.target;
      if (t && t.getAttribute && t.getAttribute("data-close") === "1") {
        el.meetingModal.classList.remove("open");
        el.meetingModal.setAttribute("aria-hidden", "true");
      }
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && el.meetingModal.classList.contains("open")) {
        el.meetingModal.classList.remove("open");
        el.meetingModal.setAttribute("aria-hidden", "true");
      }
    });
  }

  function bind() {
    el.btnPrevMonth?.addEventListener("click", () => moveMonth(-1));
    el.btnNextMonth?.addEventListener("click", () => moveMonth(1));

    el.btnDayPrev?.addEventListener("click", () => jumpToNextWeekday(-1));
    el.btnDayNext?.addEventListener("click", () => jumpToNextWeekday(1));

    el.durationSelect?.addEventListener("change", () => loadDaySlots());
    el.tzSelect?.addEventListener("change", () => loadDaySlots());

    el.meetingLinkBtn?.addEventListener("click", onMeetingLinkClick);
    el.confirmSlotsBtn?.addEventListener("click", confirmSlots);

    // ✅ UPDATED: popup mail.html
    // NOTE: If your schedule.html already uses onclick="openMailPopup()",
    // this still works fine; this listener is the fallback.
    el.sendEmailsBtn?.addEventListener("click", (e) => {
      // avoid double actions if HTML onclick exists
      e.preventDefault();
      sendEmails();
    });

    if (el.totalShortlisted) el.totalShortlisted.textContent = String(allCandidates.length);
    if (el.activeVacancyName) el.activeVacancyName.textContent = activeBatch?.job_title || "—";

    if (initialMeetingLink) setMeetingLink(initialMeetingLink);
    else regenerateMeetingLink();

    bindModalClose();
  }

  async function init() {
    let d = parseISODate(initialSelectedDateISO);
    if (!d) {
      d = addDays(new Date(), 1);
      while (!isWeekday(d)) d = addDays(d, 1);
    }

    state.viewDate = new Date(d.getFullYear(), d.getMonth(), 1);

    bind();
    selectDate(d, { keepMonth: true });
  }

  init();
})();

async function sendEmails() {
  if (!state.selectedDate) {
    return toast("Select a date first.", "warn");
  }

  const dateISO = toISODate(state.selectedDate);
  const link = state.meetingLink || "";

  const url =
    `/interview/mail?meeting_date=${encodeURIComponent(dateISO)}&meeting_link=${encodeURIComponent(link)}`;

  // ✅ Centered popup window
  const w = 560;
  const h = 460;
  const left = Math.round((window.screen.width - w) / 2);
  const top  = Math.round((window.screen.height - h) / 2);

  window.open(
    url,
    "HireNextMailPopup",
    `width=${w},height=${h},left=${left},top=${top},resizable=yes,scrollbars=yes`
  );
}