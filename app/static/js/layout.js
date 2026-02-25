/* ===============================
   Sidebar Toggle
================================= */
document.addEventListener("DOMContentLoaded", function () {

    const toggleBtn = document.getElementById("toggleSidebar");
    const sidebar = document.getElementById("sidebar");
    const mainContent = document.getElementById("mainContent");

    if (toggleBtn) {
        toggleBtn.addEventListener("click", function () {
            sidebar.classList.toggle("hidden");
            mainContent.classList.toggle("full");
        });
    }

});

/* ===============================
   Resume Screening Logic
================================= */

const SCREENINGS_MAP = {};

/* ===============================
   GLOBAL LOADER
================================= */

function showLoader() {
  const loader = document.getElementById("globalLoader");
  if (loader) loader.classList.add("active");
}

function hideLoader() {
  const loader = document.getElementById("globalLoader");
  if (loader) loader.classList.remove("active");
}

/* ===============================
   Update Dashboard Stats
================================= */
function updateStats() {

  const rows = Object.values(SCREENINGS_MAP);

  document.getElementById("totalCount").innerText = rows.length;
  document.getElementById("shortlistedCount").innerText =
    rows.filter(r => r.decision === "SHORTLIST").length;
  document.getElementById("rejectedCount").innerText =
    rows.filter(r => r.decision === "REJECT").length;
}

/* ===============================
   Render Table (Auto Sort High → Low)
================================= */
function renderTable() {

  const tbody = document.querySelector("#screeningTable tbody");
  if (!tbody) return;

  tbody.innerHTML = "";

  const sortedRows = Object.values(SCREENINGS_MAP)
    .sort((a, b) => b.final_score_pct - a.final_score_pct);

  sortedRows.forEach(row => {

    const tr = document.createElement("tr");

    const badge = row.decision === "SHORTLIST"
      ? `<span class="badge success">Shortlisted</span>`
      : `<span class="badge danger">Rejected</span>`;

    const scoreColor = row.decision === "SHORTLIST"
      ? "linear-gradient(90deg, #22c55e, #16a34a)"
      : "linear-gradient(90deg, #ef4444, #dc2626)";

    tr.innerHTML = `
      <td>
        <input type="checkbox" class="rowSelect" data-id="${row._id}">
      </td>

      <td>${row.candidate_name}</td>

      <td>
        <div class="score-bar">
          <div class="score-fill"
               style="width:${row.final_score_pct}%; background:${scoreColor}">
          </div>
          <span class="score-text">${row.final_score_pct}%</span>
        </div>
      </td>

      <td>${badge}</td>

      <td>
        <button class="btn-outline"
                onclick="openDetails('${row._id}')">
          View
        </button>

        <button class="btn-outline small"
                onclick="openPDF('${row.pdf_filename}')">
          PDF
        </button>
      </td>
    `;

    tbody.appendChild(tr);
  });

  updateStats();
}

/* ===============================
   Add Row
================================= */
function addRowToTable(row) {
  SCREENINGS_MAP[row._id] = row;
  renderTable();
}

/* ===============================
   AJAX Resume Scoring
================================= */
async function scoreResumeAJAX(formEl) {

  const status = document.getElementById("scoreStatus");
  if (status) status.textContent = "Scoring resumes...";

  showLoader();

  const formData = new FormData(formEl);

  try {

    const res = await fetch("/screening/score", {
      method: "POST",
      body: formData
    });

    const data = await res.json();

    if (!data.ok) {
      alert(data.error || "Scoring failed.");
      hideLoader();
      if (status) status.textContent = "";
      return;
    }

    if (data.rows && Array.isArray(data.rows)) {
      data.rows.forEach(row => {
        SCREENINGS_MAP[row._id] = row;
      });
      renderTable();
    }

    formEl.reset();
    if (status) status.textContent = "";

  } catch (err) {
    console.error("Score error:", err);
    alert("Something went wrong during scoring.");
  }

  hideLoader();
}

/* ===============================
   Submit Shortlist
================================= */
async function submitShortlist() {

  const selected = Array.from(document.querySelectorAll(".rowSelect"))
    .filter(cb => cb.checked)
    .map(cb => SCREENINGS_MAP[cb.dataset.id]);

  if (!selected.length) {
    alert("No candidates selected.");
    return;
  }

  showLoader();

  try {

    const res = await fetch("/screening/shortlist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ shortlisted: selected })
    });

    const data = await res.json();

    if (!data.ok) {
      alert(data.error || "Shortlist failed.");
      hideLoader();
      return;
    }

    window.location.href = data.redirect;

  } catch (err) {
    console.error("Shortlist error:", err);
    alert("Something went wrong while shortlisting.");
    hideLoader();
  }
}

/* ===============================
   Modal: Modern Candidate Details
   (LIMITED + CLEAN VERSION)
================================= */
function openDetails(id) {

  const row = SCREENINGS_MAP[id];
  if (!row) return;

  const cv = row.parsed_cv || {};

  /* -------- Limit Skills (max 8) -------- */
  const skills = (cv.skills_list || []).slice(0, 8);
  const skillsHTML = skills.length
    ? skills.map(skill => `<span class="skill-tag">${skill}</span>`).join("")
    : "Not available";

  /* -------- Limit Summary -------- */
  const summary = cv.summary
    ? (cv.summary.length > 600
        ? cv.summary.substring(0, 600) + "..."
        : cv.summary)
    : "Not available";

  /* -------- Limit Experience -------- */
  const experience = cv.experience
    ? (cv.experience.length > 800
        ? cv.experience.substring(0, 800) + "..."
        : cv.experience)
    : "Not available";

  document.getElementById("modalTop").innerHTML = `
    <div class="candidate-header">
      <div>
        <h2>${row.candidate_name}</h2>
        <p class="candidate-role">${cv.title || ""}</p>
      </div>
      <div class="candidate-meta">
        <span class="score-pill">${row.final_score_pct}%</span>
        <span class="decision-pill ${row.decision === "SHORTLIST" ? "short" : "reject"}">
          ${row.decision}
        </span>
      </div>
    </div>
  `;

  document.getElementById("parsedContent").innerHTML = `
    <div class="details-grid">

      <div class="detail-section">
        <h4>Professional Summary</h4>
        <p>${summary}</p>
      </div>

      <div class="detail-section">
        <h4>Experience</h4>
        <p>${experience}</p>
      </div>

      <div class="detail-section">
        <h4>Education</h4>
        <p>${cv.education || "Not available"}</p>
      </div>

      <div class="detail-section">
        <h4>Skills</h4>
        <div class="skill-tags">
          ${skillsHTML}
        </div>
      </div>

    </div>
  `;

  document.getElementById("detailsModal").style.display = "flex";
}

function closeDetails() {
  document.getElementById("detailsModal").style.display = "none";
}

/* ===============================
   Modal: PDF Preview
================================= */
function openPDF(filename) {
  document.getElementById("pdfFrame").src = `/screening/uploads/${filename}`;
  document.getElementById("pdfModal").style.display = "flex";
}

function closePDF() {
  document.getElementById("pdfFrame").src = "";
  document.getElementById("pdfModal").style.display = "none";
}

/* ===============================
   Reset Session
================================= */
async function resetSession() {
  await fetch("/screening/reset", { method: "POST" });
  location.reload();
}

/* ===============================
   DOM Ready
================================= */
document.addEventListener("DOMContentLoaded", () => {

  const form = document.getElementById("scoreForm");

  if (form) {
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      scoreResumeAJAX(this);
    });
  }

});