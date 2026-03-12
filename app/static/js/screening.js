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
   SweetAlert Helpers
================================= */
function showWarning(title, text) {
  Swal.fire({
    icon: "warning",
    title: title,
    text: text,
    confirmButtonColor: "#2563eb"
  });
}

function showError(title, text) {
  Swal.fire({
    icon: "error",
    title: title,
    text: text,
    confirmButtonColor: "#dc2626"
  });
}

function showSuccess(title, text) {
  Swal.fire({
    icon: "success",
    title: title,
    text: text,
    confirmButtonColor: "#16a34a"
  });
}


/* ===============================
   Update Dashboard Stats
================================= */
function updateStats() {
  const rows = Object.values(SCREENINGS_MAP);

  const totalEl = document.getElementById("totalCount");
  const shortEl = document.getElementById("shortlistedCount");
  const rejectEl = document.getElementById("rejectedCount");

  if (totalEl) totalEl.innerText = rows.length;
  if (shortEl) {
    shortEl.innerText = rows.filter(r => r.decision === "SHORTLIST").length;
  }
  if (rejectEl) {
    rejectEl.innerText = rows.filter(r => r.decision === "REJECT").length;
  }
}


/* ===============================
   Render Table
================================= */
function renderTable() {
  const tbody = document.querySelector("#screeningTable tbody");
  if (!tbody) return;

  tbody.innerHTML = "";

  const sortedRows = Object.values(SCREENINGS_MAP).sort(
    (a, b) => (b.final_score_pct || 0) - (a.final_score_pct || 0)
  );

  sortedRows.forEach(row => {
    const tr = document.createElement("tr");

    const decision = row.decision || "REJECT";
    const badge = decision === "SHORTLIST"
      ? `<span class="badge success">Shortlisted</span>`
      : `<span class="badge danger">Rejected</span>`;

    const score = Number(row.final_score_pct || 0);
    const scoreColor = decision === "SHORTLIST"
      ? "linear-gradient(90deg, #22c55e, #16a34a)"
      : "linear-gradient(90deg, #ef4444, #dc2626)";

    tr.innerHTML = `
      <td>
        <input type="checkbox" class="rowSelect" data-id="${row._id}">
      </td>

      <td>${row.candidate_name || "Candidate"}</td>

      <td>
        <div class="score-bar">
          <div class="score-fill"
               style="width:${score}%; background:${scoreColor}">
          </div>
          <span class="score-text">${score}%</span>
        </div>
      </td>

      <td>${badge}</td>

      <td>
        <button type="button" class="btn-outline" onclick="openDetails('${row._id}')">
          View
        </button>

        <button type="button" class="btn-outline small" onclick="openPDF('${row.pdf_filename || ""}')">
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
  if (!row || !row._id) return;
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
      hideLoader();
      if (status) status.textContent = "";
      showError("Scoring Failed", data.error || "Unable to score resumes.");
      return;
    }

    if (data.rows && Array.isArray(data.rows)) {
      data.rows.forEach(row => {
        if (row && row._id) {
          SCREENINGS_MAP[row._id] = row;
        }
      });

      renderTable();
      showSuccess("Scoring Completed", "Resume scoring finished successfully.");
    } else {
      showWarning("No Results", "No screening results were returned.");
    }

    formEl.reset();
    if (status) status.textContent = "";

  } catch (err) {
    console.error("Score error:", err);
    showError("Unexpected Error", "Something went wrong during resume scoring.");
  } finally {
    hideLoader();
  }
}


/* ===============================
   Submit Shortlist
================================= */
async function submitShortlist() {
  const selected = Array.from(document.querySelectorAll(".rowSelect"))
    .filter(cb => cb.checked)
    .map(cb => SCREENINGS_MAP[cb.dataset.id])
    .filter(row => row && row.decision === "SHORTLIST");

  if (!selected.length) {
    showWarning(
      "No Valid Shortlisted Candidates",
      "Please select at least one shortlisted candidate."
    );
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
      showError("Shortlist Failed", data.error || "Unable to save shortlisted candidates.");
      return;
    }

    await Swal.fire({
      icon: "success",
      title: "Shortlist Saved",
      text: "Selected candidates have been shortlisted successfully.",
      confirmButtonColor: "#16a34a"
    });

    if (data.redirect) {
      window.location.href = data.redirect;
    }

  } catch (err) {
    console.error("Shortlist error:", err);
    showError("Unexpected Error", "Something went wrong while shortlisting candidates.");
  } finally {
    hideLoader();
  }
}


/* ===============================
   Candidate Details Modal
================================= */
function openDetails(id) {
  const row = SCREENINGS_MAP[id];
  if (!row) return;

  const cv = row.parsed_cv || {};

  const skills = (cv.skills_list || []).slice(0, 8);
  const skillsHTML = skills.length
    ? skills.map(skill => `<span class="skill-tag">${skill}</span>`).join("")
    : "Not available";

  const summary = cv.summary
    ? (cv.summary.length > 600 ? cv.summary.substring(0, 600) + "..." : cv.summary)
    : "Not available";

  const experience = cv.experience
    ? (cv.experience.length > 800 ? cv.experience.substring(0, 800) + "..." : cv.experience)
    : "Not available";

  const modalTop = document.getElementById("modalTop");
  const parsedContent = document.getElementById("parsedContent");
  const modal = document.getElementById("detailsModal");

  if (!modalTop || !parsedContent || !modal) return;

  modalTop.innerHTML = `
    <div class="candidate-header">
      <div>
        <h2>${row.candidate_name || "Candidate"}</h2>
        <p class="candidate-role">${cv.title || ""}</p>
      </div>
      <div class="candidate-meta">
        <span class="score-pill">${row.final_score_pct || 0}%</span>
        <span class="decision-pill ${row.decision === "SHORTLIST" ? "short" : "reject"}">
          ${row.decision || "REJECT"}
        </span>
      </div>
    </div>
  `;

  parsedContent.innerHTML = `
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
        <div class="skill-tags">${skillsHTML}</div>
      </div>
    </div>
  `;

  modal.style.display = "flex";
}

function closeDetails() {
  const modal = document.getElementById("detailsModal");
  if (modal) modal.style.display = "none";
}


/* ===============================
   PDF Preview Modal
================================= */
function openPDF(filename) {
  if (!filename) {
    showWarning("PDF Not Found", "No resume PDF is available for preview.");
    return;
  }

  const frame = document.getElementById("pdfFrame");
  const modal = document.getElementById("pdfModal");

  if (frame) frame.src = `/screening/uploads/${filename}`;
  if (modal) modal.style.display = "flex";
}

function closePDF() {
  const frame = document.getElementById("pdfFrame");
  const modal = document.getElementById("pdfModal");

  if (frame) frame.src = "";
  if (modal) modal.style.display = "none";
}


/* ===============================
   Reset Session
================================= */
async function resetSession() {
  const result = await Swal.fire({
    icon: "question",
    title: "Reset Screening Session?",
    text: "This will clear the current screening session.",
    showCancelButton: true,
    confirmButtonColor: "#2563eb",
    cancelButtonColor: "#6b7280",
    confirmButtonText: "Yes, reset",
    cancelButtonText: "Cancel"
  });

  if (!result.isConfirmed) return;

  showLoader();

  try {
    const res = await fetch("/screening/reset", {
      method: "POST"
    });

    if (!res.ok) {
      showError("Reset Failed", "Unable to reset the screening session.");
      return;
    }

    await Swal.fire({
      icon: "success",
      title: "Session Reset",
      text: "The screening session has been reset successfully.",
      confirmButtonColor: "#16a34a"
    });

    location.reload();

  } catch (err) {
    console.error("Reset failed:", err);
    showError("Unexpected Error", "Something went wrong while resetting the session.");
  } finally {
    hideLoader();
  }
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