/* ============================= */
/* Auth Popup JS (Modal-ready)   */
/* ============================= */

(function () {
  // Helper: safely find modal body (exists on welcome page)
  function getModalBody() {
    return document.getElementById("authModalBody");
  }

  // Helper: load auth partial into modal body
  function loadAuth(url) {
    const body = getModalBody();
    if (!body) return;

    fetch(url, { headers: { "X-Requested-With": "fetch" } })
      .then((res) => res.text())
      .then((html) => {
        body.innerHTML = html;
        // After injection, reset any loading states just in case
        resetLoading(body);
      })
      .catch(() => {
        body.innerHTML =
          '<div class="auth-card popup-card"><p style="margin:0;color:#ef4444;">Failed to load. Please try again.</p></div>';
      });
  }

  function setLoading(form, isLoading) {
    const btn = form.querySelector("button[type='submit']");
    if (!btn) return;

    if (isLoading) {
      btn.dataset.originalText = btn.textContent;
      btn.textContent = "Please wait...";
      btn.disabled = true;
      btn.classList.add("is-loading");
    } else {
      btn.textContent = btn.dataset.originalText || btn.textContent;
      btn.disabled = false;
      btn.classList.remove("is-loading");
    }
  }

  function resetLoading(root) {
    root.querySelectorAll("form").forEach((form) => setLoading(form, false));
  }

  // Global listeners (work even for injected HTML)
  document.addEventListener("DOMContentLoaded", function () {
    /* ----------------------------- */
    /* Password Show / Hide          */
    /* ----------------------------- */
    document.addEventListener("click", function (e) {
      const btn = e.target.closest(".pw-toggle");
      if (!btn) return;

      const targetId = btn.getAttribute("data-target");
      const input = document.getElementById(targetId);
      if (!input) return;

      const isPassword = input.getAttribute("type") === "password";
      input.setAttribute("type", isPassword ? "text" : "password");
      btn.textContent = isPassword ? "Hide" : "Show";
    });

    /* ----------------------------- */
    /* Switch login/register in modal */
    /* ----------------------------- */
    document.addEventListener("click", function (e) {
      const link = e.target.closest(".switch-link");
      if (!link) return;

      e.preventDefault();

      const type = link.getAttribute("data-auth"); // "login" or "register"
      const url = type === "register" ? "/auth/register" : "/auth/login";
      loadAuth(url);
    });

    /* ----------------------------- */
    /* Client-side validation        */
    /* ----------------------------- */
    document.addEventListener("submit", function (e) {
      const form = e.target;
      if (!(form instanceof HTMLFormElement)) return;

      const action = form.getAttribute("action") || "";

      // Register validation
      if (action.includes("/auth/register")) {
        const passwordInput = form.querySelector("input[name='password']");
        const pw = (passwordInput?.value || "").trim();

        if (pw.length < 8) {
          e.preventDefault();
          alert("Password must be at least 8 characters.");
          return;
        }

        // Terms checkbox (required in your updated register.html)
        const terms = form.querySelector("input[type='checkbox'][required]");
        if (terms && !terms.checked) {
          e.preventDefault();
          alert("Please accept the Terms and Privacy Policy.");
          return;
        }
      }

      // Login validation (basic)
      if (action.includes("/auth/login")) {
        const email = (form.querySelector("input[name='email']")?.value || "").trim();
        const pw = (form.querySelector("input[name='password']")?.value || "").trim();

        if (!email || !pw) {
          e.preventDefault();
          alert("Please enter your email and password.");
          return;
        }
      }

      // Prevent double submit + show loading
      setLoading(form, true);
    });
  });

  // Expose loader optionally if you want to call it from welcome.js
  window.AuthPopup = {
    load: loadAuth,
  };
})(); 