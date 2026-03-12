document.addEventListener("DOMContentLoaded", () => {
  const searchInput = document.getElementById("staffSearch");
  const tableBody = document.getElementById("staffTableBody");

  if (searchInput && tableBody) {
    searchInput.addEventListener("input", function () {
      const value = this.value.toLowerCase().trim();
      const rows = tableBody.querySelectorAll("tr");

      rows.forEach((row) => {
        const text = row.innerText.toLowerCase();
        row.style.display = text.includes(value) ? "" : "none";
      });
    });
  }

  // simple count animation
  const counters = [
    { id: "totalStaff", target: 56 },
    { id: "totalVacancies", target: 24 },
    { id: "totalOrgs", target: 12 },
    { id: "activeRecruiters", target: 18 }
  ];

  counters.forEach(counter => animateCounter(counter.id, counter.target, 1000));

  function animateCounter(id, target, duration) {
    const el = document.getElementById(id);
    if (!el) return;

    let start = 0;
    const stepTime = Math.max(Math.floor(duration / target), 20);

    const timer = setInterval(() => {
      start += 1;
      el.textContent = start;

      if (start >= target) {
        el.textContent = target;
        clearInterval(timer);
      }
    }, stepTime);
  }

  // action button demo
  document.querySelectorAll(".action-btn.edit").forEach(btn => {
    btn.addEventListener("click", () => {
      alert("Edit staff member");
    });
  });

  document.querySelectorAll(".action-btn.view").forEach(btn => {
    btn.addEventListener("click", () => {
      alert("View staff details");
    });
  });

  document.querySelectorAll(".action-btn.delete").forEach(btn => {
    btn.addEventListener("click", () => {
      const ok = confirm("Are you sure you want to remove this staff member?");
      if (ok) {
        alert("Staff member removed");
      }
    });
  });

  const notifyBtn = document.getElementById("notifyBtn");
  if (notifyBtn) {
    notifyBtn.addEventListener("click", () => {
      alert("You have 3 new admin notifications.");
    });
  }
});