/* ===============================
   Resume Screening State
================================= */
const SCREENINGS_MAP = {};


/* ===============================
   SweetAlert Helper
================================= */
function hasSwal() {
  return typeof Swal !== "undefined";
}

function showErrorAlert(message) {
  if (hasSwal()) {
    Swal.fire({
      icon: "error",
      title: "Error",
      text: message
    });
  } else {
    alert(message);
  }
}

function showWarningAlert(message) {
  if (hasSwal()) {
    Swal.fire({
      icon: "warning",
      title: "Warning",
      text: message
    });
  } else {
    alert(message);
  }
}

function showSuccessAlert(message) {
  if (hasSwal()) {
    Swal.fire({
      icon: "success",
      title: "Success",
      text: message
    });
  } else {
    alert(message);
  }
}


/* ===============================
   Global Loader
================================= */
function showLoader() {
  const loader = document.getElementById("globalLoader");
  if (loader) {
    loader.classList.add("active");
  }
}

function hideLoader() {
  const loader = document.getElementById("globalLoader");
  if (loader) {
    loader.classList.remove("active");
  }
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
  if (shortEl) shortEl.innerText = rows.filter((r) => r.decision === "SHORTLIST").length;
  if (rejectEl) rejectEl.innerText = rows.filter((r) => r.decision === "REJECT").length;
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

  sortedRows.forEach((row) => {
    const tr = document.createElement("tr");

    const decision = row.decision || "REJECT";
    const badge =
      decision === "SHORTLIST"
        ? `<span class="badge success">Shortlisted</span>`
        : `<span class="badge danger">Rejected</span>`;

    const score = Number(row.final_score_pct || 0);
    const scoreColor =
      decision === "SHORTLIST"
        ? "linear-gradient(90deg, #22c55e, #16a34a)"
        : "linear-gradient(90deg, #ef4444, #dc2626)";

    tr.innerHTML = `
      <td>
        <input type="checkbox" class="rowSelect" data-id="${row._id}">
      </td>

      <td>${row.candidate_name || "Candidate"}</td>

      <td>
        <div class="score-bar">
          <div class="score-fill" style="width:${score}%; background:${scoreColor}"></div>
          <span class="score-text">${score}%</span>
        </div>
      </td>

      <td>${badge}</td>

      <td>
        <button class="btn-outline" type="button" onclick="openDetails('${row._id}')">
          View
        </button>

        <button class="btn-outline small" type="button" onclick="openPDF('${row.pdf_filename || ""}')">
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

  if (status) {
    status.textContent = "Scoring resumes...";
  }

  showLoader();

  try {
    const formData = new FormData(formEl);

    const res = await fetch("/screening/score", {
      method: "POST",
      body: formData
    });

    const data = await res.json();

    if (!data.ok) {
      showErrorAlert(data.error || "Scoring failed.");
      return;
    }

    if (Array.isArray(data.rows)) {
      data.rows.forEach((row) => {
        if (row && row._id) {
          SCREENINGS_MAP[row._id] = row;
        }
      });
      renderTable();
    }

    formEl.reset();

    if (hasSwal()) {
      Swal.fire({
        icon: "success",
        title: "Completed",
        text: "Resume scoring finished successfully.",
        timer: 1600,
        showConfirmButton: false
      });
    }
  } catch (err) {
    console.error("Score error:", err);
    showErrorAlert("Something went wrong during scoring.");
  } finally {
    if (status) {
      status.textContent = "";
    }
    hideLoader();
  }
}


/* ===============================
   Submit Shortlist
================================= */
async function submitShortlist() {
  const selected = Array.from(document.querySelectorAll(".rowSelect"))
    .filter((cb) => cb.checked)
    .map((cb) => SCREENINGS_MAP[cb.dataset.id])
    .filter(Boolean);

  if (!selected.length) {
    showWarningAlert("No candidates selected.");
    return;
  }

  showLoader();

  try {
    const res = await fetch("/screening/shortlist", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ shortlisted: selected })
    });

    const data = await res.json();

    if (!data.ok) {
      showErrorAlert(data.error || "Shortlist failed.");
      return;
    }

    if (hasSwal()) {
      await Swal.fire({
        icon: "success",
        title: "Shortlist Submitted",
        text: "Selected candidates have been shortlisted successfully.",
        timer: 1500,
        showConfirmButton: false
      });
    }

    if (data.redirect) {
      window.location.href = data.redirect;
    }
  } catch (err) {
    console.error("Shortlist error:", err);
    showErrorAlert("Something went wrong while shortlisting.");
  } finally {
    hideLoader();
  }
}


/* ===============================
   Modal: Candidate Details
================================= */
function openDetails(id) {
  const row = SCREENINGS_MAP[id];
  if (!row) return;

  const cv = row.parsed_cv || {};

  const skills = (cv.skills_list || []).slice(0, 8);
  const skillsHTML = skills.length
    ? skills.map((skill) => `<span class="skill-tag">${skill}</span>`).join("")
    : "Not available";

  const summary = cv.summary
    ? (cv.summary.length > 600 ? `${cv.summary.substring(0, 600)}...` : cv.summary)
    : "Not available";

  const experience = cv.experience
    ? (cv.experience.length > 800 ? `${cv.experience.substring(0, 800)}...` : cv.experience)
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
  if (modal) {
    modal.style.display = "none";
  }
}


/* ===============================
   Modal: PDF Preview
================================= */
function openPDF(filename) {
  if (!filename) return;

  const frame = document.getElementById("pdfFrame");
  const modal = document.getElementById("pdfModal");

  if (frame) {
    frame.src = `/screening/uploads/${filename}`;
  }

  if (modal) {
    modal.style.display = "flex";
  }
}

function closePDF() {
  const frame = document.getElementById("pdfFrame");
  const modal = document.getElementById("pdfModal");

  if (frame) {
    frame.src = "";
  }

  if (modal) {
    modal.style.display = "none";
  }
}


/* ===============================
   Reset Session
================================= */
async function resetSession() {
  if (hasSwal()) {
    const result = await Swal.fire({
      title: "Reset session?",
      text: "This will clear the current screening session.",
      icon: "warning",
      showCancelButton: true,
      confirmButtonColor: "#ef4444",
      cancelButtonColor: "#6b7280",
      confirmButtonText: "Yes, reset it",
      cancelButtonText: "Cancel",
      reverseButtons: true
    });

    if (!result.isConfirmed) return;
  } else {
    const ok = confirm("This will clear the current screening session. Continue?");
    if (!ok) return;
  }

  showLoader();

  try {
    await fetch("/screening/reset", {
      method: "POST"
    });

    if (hasSwal()) {
      await Swal.fire({
        icon: "success",
        title: "Reset Done",
        text: "Session has been cleared successfully.",
        timer: 1400,
        showConfirmButton: false
      });
    }

    location.reload();
  } catch (e) {
    console.warn("Reset failed:", e);
    showErrorAlert("Reset failed. Please try again.");
    hideLoader();
  }
}


/* ===============================
   Logout Confirmation
================================= */
async function handleLogout(event) {
  if (event) {
    event.preventDefault();
  }

  const logoutUrl = event && event.currentTarget ? event.currentTarget.href : null;

  if (!logoutUrl) {
    showErrorAlert("Logout link not found.");
    return;
  }

  if (hasSwal()) {
    const result = await Swal.fire({
      title: "Are you sure?",
      text: "You will be logged out of the system.",
      icon: "warning",
      showCancelButton: true,
      confirmButtonColor: "#ef4444",
      cancelButtonColor: "#6b7280",
      confirmButtonText: "Yes, logout",
      cancelButtonText: "Cancel",
      reverseButtons: true
    });

    if (!result.isConfirmed) return;

    await Swal.fire({
      icon: "success",
      title: "Logged Out",
      text: "You have been successfully logged out.",
      timer: 1200,
      showConfirmButton: false
    });
  } else {
    const ok = confirm("Are you sure you want to logout?");
    if (!ok) return;
  }

  showLoader();
  window.location.href = logoutUrl;
}


/* ===============================
   DOM Ready
================================= */
document.addEventListener("DOMContentLoaded", function () {
  const toggleBtn = document.getElementById("toggleSidebar");
  const sidebar = document.getElementById("sidebar");
  const mainContent = document.getElementById("mainContent");
  const footer = document.getElementById("footer");

  if (toggleBtn && sidebar && mainContent) {
    toggleBtn.addEventListener("click", function () {
      sidebar.classList.toggle("active");
      mainContent.classList.toggle("shifted");

      if (footer) {
        footer.classList.toggle("shifted");
      }
    });
  }

  const form = document.getElementById("scoreForm");
  if (form) {
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      scoreResumeAJAX(this);
    });
  }

  const logoutBtn = document.getElementById("logoutBtn");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", handleLogout);
  }
});