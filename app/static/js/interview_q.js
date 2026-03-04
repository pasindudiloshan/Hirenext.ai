/* app/static/js/interview_q.js
   ✅ Stacked questions (append one-by-one)
   ✅ Only bottom countdown (no top countdown / no stepper)
   ✅ After countdown: redirect to interview.html
*/

document.addEventListener("DOMContentLoaded", () => {
  const ctx = window.__INTERVIEW_PREVIEW_CTX__ || {};

  const role = String(ctx.role || "Interview");
  const topics = Array.isArray(ctx.topics) ? ctx.topics : [];
  const questionsRaw = Array.isArray(ctx.questions) ? ctx.questions : [];
  const redirectUrl = String(ctx.redirectUrl || "");
  const showEachMs = Number(ctx.showEachQuestionMs || 1800);
  const countdownSec = Number(ctx.afterLastCountdownSec || 3);

  // Elements
  const el = {
    roleTitle: document.getElementById("iqRoleTitle"),
    roleSub: document.getElementById("iqRoleSub"),
    topics: document.getElementById("iqTopics"),
    totalQ: document.getElementById("iqTotalQ"),

    qMeta: document.getElementById("iqQMeta"),
    qList: document.getElementById("iqQList"),

    bottomText: document.getElementById("iqBottomText"),
    bottomCountdown: document.getElementById("iqBottomCountdown"),
    bottomNum: document.getElementById("iqBottomNum"),
  };

  // Helpers: normalize questions into objects
  function normalizeQuestion(item) {
    // supports: string OR dict
    if (typeof item === "string") {
      return { question: item, skill: "", difficulty: "", id: "" };
    }
    if (item && typeof item === "object") {
      return {
        question: String(item.question || item.text || "Question"),
        skill: String(item.skill || ""),
        difficulty: String(item.difficulty || ""),
        id: String(item.id || item.question_id || ""),
      };
    }
    return { question: "Question", skill: "", difficulty: "", id: "" };
  }

  const safeQuestions = questionsRaw.length
    ? questionsRaw.map(normalizeQuestion)
    : [
        { question: "Loading questions…", skill: "", difficulty: "" },
        { question: "Preparing the session…", skill: "", difficulty: "" },
        { question: "Almost ready…", skill: "", difficulty: "" },
      ];

  // Fill role/title
  if (el.roleTitle) el.roleTitle.textContent = role;
  if (el.roleSub) el.roleSub.textContent = "Interview Q&A Preview";
  if (el.totalQ) el.totalQ.textContent = String(safeQuestions.length);

  // Topics chips
  if (el.topics) {
    el.topics.innerHTML = "";
    (topics.length ? topics : ["General"]).forEach((t) => {
      const chip = document.createElement("span");
      chip.className = "iq-chip";
      chip.textContent = String(t);
      el.topics.appendChild(chip);
    });
  }

  // Guard
  if (!el.qList) return;

  // Build one stacked card
  function buildQuestionCard(q, index) {
    const card = document.createElement("div");
    card.className = "iq-item"; // animation: starts hidden, add .show later

    const num = document.createElement("div");
    num.className = "iq-item-num";
    num.textContent = `Q${index + 1}`;

    const body = document.createElement("div");
    body.className = "iq-item-body";

    const title = document.createElement("div");
    title.className = "iq-item-title";
    title.textContent = q.question;

    const meta = document.createElement("div");
    meta.className = "iq-item-meta";

    // Optional pills
    const pills = [];
    if (q.skill) pills.push({ label: q.skill });
    if (q.difficulty) pills.push({ label: q.difficulty });
    if (q.id) pills.push({ label: q.id });

    pills.forEach((p) => {
      const pill = document.createElement("span");
      pill.className = "iq-pill";
      pill.textContent = p.label;
      meta.appendChild(pill);
    });

    body.appendChild(title);
    if (pills.length) body.appendChild(meta);

    card.appendChild(num);
    card.appendChild(body);

    return card;
  }

  // Append + animate
  function appendQuestion(index) {
    const q = safeQuestions[index];

    if (el.qMeta) {
      el.qMeta.textContent = `Question ${index + 1} of ${safeQuestions.length}`;
    }

    const card = buildQuestionCard(q, index);
    el.qList.appendChild(card);

    // trigger animation
    requestAnimationFrame(() => {
      card.classList.add("show");
    });

    // smooth scroll to newest card
    setTimeout(() => {
      try {
        card.scrollIntoView({ behavior: "smooth", block: "end" });
      } catch (e) {}
    }, 250);
  }

  // Start sequence
  let idx = 0;
  el.qList.innerHTML = "";
  appendQuestion(idx);

  const timer = setInterval(() => {
    idx += 1;

    if (idx >= safeQuestions.length) {
      clearInterval(timer);
      startCountdownThenRedirect();
      return;
    }

    appendQuestion(idx);
  }, showEachMs);

  // Countdown (BOTTOM ONLY)
  function startCountdownThenRedirect() {
    if (el.qMeta) el.qMeta.textContent = `All questions loaded (${safeQuestions.length})`;

    if (el.bottomText) el.bottomText.textContent = "Final checks…";
    if (el.bottomCountdown) el.bottomCountdown.style.display = "flex";

    let n = countdownSec;
    if (el.bottomNum) el.bottomNum.textContent = String(n);

    const t = setInterval(() => {
      n -= 1;

      if (n <= 0) {
        clearInterval(t);
        if (el.bottomText) el.bottomText.textContent = "Starting interview…";
        doRedirect();
        return;
      }

      if (el.bottomNum) el.bottomNum.textContent = String(n);
    }, 1000);
  }

  function doRedirect() {
    if (!redirectUrl) return;
    setTimeout(() => {
      window.location.href = redirectUrl;
    }, 250);
  }
});