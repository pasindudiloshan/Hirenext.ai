/* static/js/calander.js
   ✅ Updated per your request:
   - Click ANY date cell → opens "Day Details" popup modal
     → shows all interviews for that date (or "No interviews available")
   - Click an interview row inside popup → redirects to:
       /interview/meeting/<interview_id>
   - Keeps your existing behavior:
     - merges backend events (window.__CAL_EVENTS__) + localStorage events
     - saves ONLY local events back to localStorage
     - Add Schedule modal still works
*/

document.addEventListener("DOMContentLoaded", () => {
  const el = {
    calTitle: document.getElementById("calTitle"),
    calGrid: document.getElementById("calGrid"),

    btnPrev: document.getElementById("btnPrev"),
    btnNext: document.getElementById("btnNext"),
    btnToday: document.getElementById("btnToday"),

    viewMonth: document.getElementById("viewMonth"),
    viewWeek: document.getElementById("viewWeek"),
    viewDay: document.getElementById("viewDay"),

    btnAddSchedule: document.getElementById("btnAddSchedule"),

    // Add Schedule modal
    modal: document.getElementById("scheduleModal"),
    form: document.getElementById("scheduleForm"),
    evTitle: document.getElementById("evTitle"),
    evType: document.getElementById("evType"),
    evDate: document.getElementById("evDate"),
    evTime: document.getElementById("evTime"),
    evDuration: document.getElementById("evDuration"),
    evNotes: document.getElementById("evNotes"),

    // ✅ Day Details modal (NEW in calander.html)
    dayModal: document.getElementById("dayDetailsModal"),
    dayTitle: document.getElementById("dayDetailsTitle"),
    daySubtitle: document.getElementById("dayDetailsSubtitle"),
    dayList: document.getElementById("dayDetailsList"),
    dayEmpty: document.getElementById("dayDetailsEmpty"),
  };

  if (!el.calGrid || !el.calTitle) return;

  const STORAGE_KEY = "hirenext_calendar_events_v2";

  const state = {
    view: "month",
    anchor: new Date(),
    selectedISO: isoDate(new Date()),
    events: [], // merged (backend + local)
  };

  function pad(n) { return String(n).padStart(2, "0"); }

  function isoDate(d) {
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  }

  function parseISO(iso) {
    const [y, m, d] = String(iso || "").split("-").map(Number);
    if (!y || !m || !d) return null;
    return new Date(y, m - 1, d, 0, 0, 0, 0);
  }

  function monthTitle(d) {
    return d.toLocaleDateString([], { month: "long", year: "numeric" });
  }

  function prettyDateLabel(iso) {
    const d = parseISO(iso);
    if (!d) return iso || "";
    return d.toLocaleDateString([], { weekday: "long", day: "2-digit", month: "short", year: "numeric" });
  }

  function startOfMonth(d) {
    return new Date(d.getFullYear(), d.getMonth(), 1);
  }

  function daysInMonth(d) {
    return new Date(d.getFullYear(), d.getMonth() + 1, 0).getDate();
  }

  function escapeHtml(s) {
    return String(s ?? "").replace(/[&<>"']/g, (m) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;"
    }[m]));
  }

  function uid() {
    return "ev_" + Math.random().toString(16).slice(2) + "_" + Date.now().toString(16);
  }

  function timeToLabel(hhmm) {
    const [h, m] = String(hhmm).split(":").map(Number);
    if (!Number.isFinite(h) || !Number.isFinite(m)) return "10a";
    const ampm = h >= 12 ? "p" : "a";
    const hh = ((h + 11) % 12) + 1;
    return `${hh}${m ? ":" + pad(m) : ""}${ampm}`;
  }

  function safeTimeFromISO(iso) {
    if (!iso) return "";
    const dt = new Date(iso);
    if (isNaN(dt.getTime())) return "";
    return `${pad(dt.getHours())}:${pad(dt.getMinutes())}`;
  }

  // ---------- Normalization ----------
  function normalizeIncoming(list, source) {
    const arr = Array.isArray(list) ? list : [];

    return arr.map((x) => {
      const date = String(x?.date || "");
      let time = String(x?.time || "");
      if (!time) time = safeTimeFromISO(x?.start_time);

      const title = String(x?.title || "Interview");

      return {
        id: String(x?.id || x?._id || uid()),
        title,
        date,
        time: time || "10:00",
        color: String(x?.color || "#5b5bd6"),
        notes: String(x?.notes || x?.candidate_email || ""),
        type: String(x?.type || "Interview"),
        duration: Number(x?.duration || 30),
        start_time: String(x?.start_time || ""),
        end_time: String(x?.end_time || ""),
        source: source || "backend", // backend | local
      };
    }).filter(e => e.date && e.time && e.title);
  }

  // ---------- Storage (ONLY local) ----------
  function loadSavedLocal() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return [];
      return normalizeIncoming(JSON.parse(raw), "local");
    } catch {
      return [];
    }
  }

  function saveLocalEventsOnly() {
    try {
      const locals = state.events.filter(ev => ev.source === "local");
      localStorage.setItem(STORAGE_KEY, JSON.stringify(locals));
    } catch {}
  }

  // ---------- Helpers ----------
  function buildByDate() {
    const byDate = new Map();
    state.events.forEach(ev => {
      const key = String(ev.date);
      if (!byDate.has(key)) byDate.set(key, []);
      byDate.get(key).push(ev);
    });
    byDate.forEach(list => list.sort((a, b) => String(a.time).localeCompare(String(b.time))));
    return byDate;
  }

  function isBackendInterview(ev) {
    return ev && ev.source === "backend" && typeof ev.id === "string" && ev.id.trim().length > 0;
  }

  function goToMeeting(ev) {
    if (!ev) return;

    // ✅ Backend interviews redirect to meeting editor
    if (isBackendInterview(ev)) {
      const id = encodeURIComponent(ev.id);
      window.location.href = `/interview/meeting/${id}`;
      return;
    }

    // Local-only schedule entries are not editable server-side
    const msg =
      `Local schedule item (not saved in database)\n\n` +
      `${ev.title}\nDate: ${ev.date}\nTime: ${ev.time}\nType: ${ev.type}\n` +
      (ev.notes ? `Notes: ${ev.notes}\n` : "");
    window.alert(msg);
  }

  // ---------- Day Details Modal ----------
  function openDayModal(iso) {
    if (!el.dayModal) return;

    const byDate = buildByDate();
    const list = (byDate.get(String(iso)) || []).slice(); // copy
    el.dayTitle && (el.dayTitle.textContent = "Interviews");
    el.daySubtitle && (el.daySubtitle.textContent = prettyDateLabel(iso));

    // Clear
    if (el.dayList) el.dayList.innerHTML = "";
    if (el.dayEmpty) el.dayEmpty.style.display = "none";

    if (!list.length) {
      if (el.dayEmpty) el.dayEmpty.style.display = "block";
    } else if (el.dayList) {
      el.dayList.innerHTML = list.map((ev) => {
        const badge =
          ev.type ? `<span class="sf-badge">${escapeHtml(ev.type)}</span>` : "";

        const notes = (ev.notes || "").trim();
        const notesHtml = notes
          ? `<div class="sf-day-row-notes">${escapeHtml(notes)}</div>`
          : "";

        const dbHint = isBackendInterview(ev)
          ? `<span class="sf-dot ok" title="Stored interview"></span>`
          : `<span class="sf-dot local" title="Local only"></span>`;

        return `
          <button class="sf-day-row"
                  type="button"
                  data-id="${escapeHtml(ev.id)}"
                  data-source="${escapeHtml(ev.source)}">
            <div class="sf-day-row-left">
              ${dbHint}
              <div class="sf-day-row-time">${escapeHtml(ev.time)}</div>
            </div>
            <div class="sf-day-row-mid">
              <div class="sf-day-row-title">${escapeHtml(ev.title)}</div>
              ${notesHtml}
            </div>
            <div class="sf-day-row-right">
              ${badge}
              <span class="sf-chevron">›</span>
            </div>
          </button>
        `;
      }).join("");

      // Bind row click → redirect
      el.dayList.querySelectorAll(".sf-day-row").forEach((btn) => {
        btn.addEventListener("click", () => {
          const id = btn.getAttribute("data-id") || "";
          const src = btn.getAttribute("data-source") || "";

          const ev = state.events.find((x) => String(x.id) === String(id) && String(x.source) === String(src))
            || state.events.find((x) => String(x.id) === String(id));

          goToMeeting(ev);
        });
      });
    }

    el.dayModal.classList.add("open");
    el.dayModal.setAttribute("aria-hidden", "false");
  }

  function closeDayModal() {
    if (!el.dayModal) return;
    el.dayModal.classList.remove("open");
    el.dayModal.setAttribute("aria-hidden", "true");
  }

  function bindDayModalClose() {
    if (!el.dayModal) return;

    el.dayModal.querySelectorAll("[data-close-day='1']").forEach(x => {
      x.addEventListener("click", closeDayModal);
    });
  }

  // ---------- View Toggle ----------
  function setActiveView(view) {
    state.view = view;

    [el.viewMonth, el.viewWeek, el.viewDay].forEach(b => b && b.classList.remove("active"));
    if (view === "month") el.viewMonth?.classList.add("active");
    if (view === "week") el.viewWeek?.classList.add("active");
    if (view === "day") el.viewDay?.classList.add("active");

    render();
  }

  // ---------- Rendering ----------
  function render() {
    el.calTitle.textContent = monthTitle(state.anchor);

    const first = startOfMonth(state.anchor);
    const firstWeekday = first.getDay();
    const dim = daysInMonth(state.anchor);

    const prevLast = new Date(state.anchor.getFullYear(), state.anchor.getMonth(), 0);
    const prevDim = prevLast.getDate();

    const cells = [];
    for (let i = 0; i < 42; i++) {
      const dayNum = i - firstWeekday + 1;
      let cellDate;
      let inMonth = true;

      if (dayNum < 1) {
        cellDate = new Date(state.anchor.getFullYear(), state.anchor.getMonth() - 1, prevDim + dayNum);
        inMonth = false;
      } else if (dayNum > dim) {
        cellDate = new Date(state.anchor.getFullYear(), state.anchor.getMonth() + 1, dayNum - dim);
        inMonth = false;
      } else {
        cellDate = new Date(state.anchor.getFullYear(), state.anchor.getMonth(), dayNum);
      }

      const iso = isoDate(cellDate);
      const isToday = iso === isoDate(new Date());
      const isSelected = iso === state.selectedISO;

      cells.push({
        iso,
        label: cellDate.getDate(),
        inMonth,
        isToday,
        isSelected,
        weekIndex: Math.floor(i / 7),
      });
    }

    let visibleCells = cells;

    if (state.view === "week") {
      const selCell = cells.find(c => c.iso === state.selectedISO) || cells[0];
      visibleCells = cells.filter(c => c.weekIndex === selCell.weekIndex);
      el.calGrid.style.gridAutoRows = "150px";
      el.calGrid.style.gridTemplateColumns = "repeat(7, 1fr)";
    } else if (state.view === "day") {
      const selCell = cells.find(c => c.iso === state.selectedISO) || cells[0];
      visibleCells = cells.filter(c => c.iso === selCell.iso);
      el.calGrid.style.gridAutoRows = "520px";
      el.calGrid.style.gridTemplateColumns = "1fr";
    } else {
      el.calGrid.style.gridAutoRows = "118px";
      el.calGrid.style.gridTemplateColumns = "repeat(7, 1fr)";
    }

    const byDate = buildByDate();

    el.calGrid.innerHTML = visibleCells.map(c => {
      const dayEvents = byDate.get(c.iso) || [];
      const showEvents = dayEvents.slice(0, state.view === "day" ? 10 : 3);

      const classes = [
        "sf-day",
        c.inMonth ? "" : "muted",
        c.isToday ? "today" : "",
        c.isSelected ? "selected" : "",
        "clickable"
      ].filter(Boolean).join(" ");

      return `
        <div class="${classes}" data-iso="${c.iso}">
          <div class="num ${c.inMonth ? "in-month" : ""}">${c.label}</div>
          <div class="sf-events">
            ${showEvents.map(ev => `
              <div class="sf-event"
                   data-id="${escapeHtml(ev.id)}"
                   data-source="${escapeHtml(ev.source)}"
                   title="${escapeHtml(ev.title)}"
                   style="background:${escapeHtml(ev.color)}">
                ${escapeHtml(ev.title)}
              </div>
            `).join("")}

            ${dayEvents.length > showEvents.length ? `
              <div class="sf-event gray" title="More events">
                +${dayEvents.length - showEvents.length} more
              </div>
            ` : ""}
          </div>
        </div>
      `;
    }).join("");

    // ✅ Click handlers:
    // - clicking day cell opens day modal
    // - clicking event pill stops propagation and opens day modal too (and user can click the row to redirect)
    el.calGrid.querySelectorAll(".sf-day").forEach(dayEl => {
      dayEl.addEventListener("click", (e) => {
        const iso = dayEl.getAttribute("data-iso");
        if (!iso) return;

        // if clicked pill, handle separately
        const pill = e.target.closest(".sf-event");
        if (pill) {
          e.preventDefault();
          e.stopPropagation();
          state.selectedISO = iso;

          // keep anchor aligned when clicking outside month
          if (state.view === "month") {
            const d = parseISO(iso);
            if (d && (d.getMonth() !== state.anchor.getMonth() || d.getFullYear() !== state.anchor.getFullYear())) {
              state.anchor = new Date(d.getFullYear(), d.getMonth(), 1);
            }
          }

          render();
          openDayModal(iso);
          return;
        }

        // normal day click
        state.selectedISO = iso;

        if (state.view === "month") {
          const d = parseISO(iso);
          if (d && (d.getMonth() !== state.anchor.getMonth() || d.getFullYear() !== state.anchor.getFullYear())) {
            state.anchor = new Date(d.getFullYear(), d.getMonth(), 1);
          }
        }

        render();
        openDayModal(iso);
      });
    });
  }

  // ---------- Navigation ----------
  function goToday() {
    const now = new Date();
    state.anchor = new Date(now.getFullYear(), now.getMonth(), 1);
    state.selectedISO = isoDate(now);
    render();
    openDayModal(state.selectedISO);
  }

  function moveMonth(delta) {
    const d = new Date(state.anchor);
    d.setMonth(d.getMonth() + delta, 1);
    state.anchor = d;

    const sel = parseISO(state.selectedISO);
    if (!sel || sel.getMonth() !== d.getMonth() || sel.getFullYear() !== d.getFullYear()) {
      state.selectedISO = isoDate(new Date(d.getFullYear(), d.getMonth(), 1));
    }
    render();
  }

  // ---------- Add Schedule Modal ----------
  function openModal() {
    if (!el.modal) return;
    el.modal.classList.add("open");
    el.modal.setAttribute("aria-hidden", "false");

    if (el.evDate) el.evDate.value = state.selectedISO;
    if (el.evTime && !el.evTime.value) el.evTime.value = "10:00";
    el.evTitle?.focus();
  }

  function closeModal() {
    if (!el.modal) return;
    el.modal.classList.remove("open");
    el.modal.setAttribute("aria-hidden", "true");
  }

  function bindModalClose() {
    if (!el.modal) return;

    el.modal.querySelectorAll("[data-close='1']").forEach(x => {
      x.addEventListener("click", closeModal);
    });
  }

  // ---------- Add local event ----------
  function addEventFromForm() {
    const title = (el.evTitle?.value || "").trim();
    const type = (el.evType?.value || "Interview").trim();
    const date = (el.evDate?.value || "").trim();
    const time = (el.evTime?.value || "").trim();
    const dur = Number(el.evDuration?.value || 30);
    const notes = (el.evNotes?.value || "").trim();

    if (!title || !date || !time) return;

    const prettyTitle =
      /interview|meeting|phone|video/i.test(title)
        ? title
        : `${timeToLabel(time)} ${type.toLowerCase()} - ${title}`;

    const ev = {
      id: uid(),
      title: prettyTitle,
      date,
      time,
      duration: dur,
      notes,
      color: "#5b5bd6",
      type,
      start_time: "",
      end_time: "",
      source: "local",
    };

    state.events.push(ev);
    saveLocalEventsOnly();

    const d = parseISO(date);
    if (d) state.anchor = new Date(d.getFullYear(), d.getMonth(), 1);
    state.selectedISO = date;

    render();
    closeModal();
    openDayModal(state.selectedISO);

    if (el.evTitle) el.evTitle.value = "";
    if (el.evNotes) el.evNotes.value = "";
  }

  // ---------- Bindings ----------
  function bind() {
    el.btnPrev?.addEventListener("click", () => moveMonth(-1));
    el.btnNext?.addEventListener("click", () => moveMonth(1));
    el.btnToday?.addEventListener("click", goToday);

    el.viewMonth?.addEventListener("click", () => setActiveView("month"));
    el.viewWeek?.addEventListener("click", () => setActiveView("week"));
    el.viewDay?.addEventListener("click", () => setActiveView("day"));

    el.btnAddSchedule?.addEventListener("click", openModal);

    el.form?.addEventListener("submit", (e) => {
      e.preventDefault();
      addEventFromForm();
    });

    bindModalClose();
    bindDayModalClose();

    // ✅ ESC key closes whichever modal is open
    document.addEventListener("keydown", (e) => {
      if (e.key !== "Escape") return;
      if (el.dayModal?.classList.contains("open")) closeDayModal();
      if (el.modal?.classList.contains("open")) closeModal();
    });
  }

  // ---------- Init ----------
  function init() {
    const backend = normalizeIncoming(window.__CAL_EVENTS__ || [], "backend");
    const savedLocal = loadSavedLocal();

    // Deduplicate: prefer ID, fallback to (date|time|title)
    const seen = new Set();
    const merged = [];

    function keyOf(ev) {
      const id = String(ev.id || "").trim();
      if (id) return `id:${id}`;
      return `k:${ev.date}|${ev.time}|${ev.title}`.toLowerCase();
    }

    [...backend, ...savedLocal].forEach(ev => {
      const k = keyOf(ev);
      if (seen.has(k)) return;
      seen.add(k);
      merged.push(ev);
    });

    state.events = merged;

    const now = new Date();
    state.anchor = new Date(now.getFullYear(), now.getMonth(), 1);
    state.selectedISO = isoDate(now);

    bind();
    setActiveView("month");
  }

  init();
});