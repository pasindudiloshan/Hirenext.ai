/* =========================
   HireNext Welcome Page JS
   - Auth modal integration
   - 4 image autoplay slider
   - Animated counters
========================= */

(function () {

  document.addEventListener("DOMContentLoaded", function () {

    /* =====================================================
       AUTH MODAL
    ===================================================== */

    const modal = document.getElementById("authModal");
    const modalBody = document.getElementById("authModalBody");
    const closeBtn = document.querySelector(".auth-close");

    function openAuth(type) {
      if (!modal || !modalBody) return;

      const url = type === "register"
        ? "/auth/register"
        : "/auth/login";

      modal.classList.remove("hidden");
      modal.setAttribute("aria-hidden", "false");

      // Use AuthPopup loader if available
      if (window.AuthPopup && typeof window.AuthPopup.load === "function") {
        window.AuthPopup.load(url);
        return;
      }

      // Fallback fetch
      fetch(url)
        .then(res => res.text())
        .then(html => {
          modalBody.innerHTML = html;
        })
        .catch(() => {
          modalBody.innerHTML =
            '<div class="auth-card popup-card"><p style="margin:0;color:#ef4444;">Failed to load. Please try again.</p></div>';
        });
    }

    function closeModal() {
      if (!modal) return;
      modal.classList.add("hidden");
      modal.setAttribute("aria-hidden", "true");
      if (modalBody) modalBody.innerHTML = "";
    }

    // Buttons
    const loginBtn = document.getElementById("openLogin");
    const registerBtn = document.getElementById("openRegister");
    const getStartedBtn = document.getElementById("openGetStarted");

    if (loginBtn) {
      loginBtn.addEventListener("click", function (e) {
        e.preventDefault();
        openAuth("login");
      });
    }

    if (registerBtn) {
      registerBtn.addEventListener("click", function (e) {
        e.preventDefault();
        openAuth("register");
      });
    }

    if (getStartedBtn) {
      getStartedBtn.addEventListener("click", function (e) {
        e.preventDefault();
        openAuth("login");
      });
    }

    if (closeBtn) {
      closeBtn.addEventListener("click", closeModal);
    }

    window.addEventListener("click", function (e) {
      if (e.target === modal) closeModal();
    });

    window.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && modal && !modal.classList.contains("hidden")) {
        closeModal();
      }
    });


    /* =====================================================
       SLIDER
    ===================================================== */

    const slider = document.getElementById("hnSlider");

    if (slider) {
      const slides = Array.from(slider.querySelectorAll(".slide"));
      const dotsWrap = document.getElementById("hnSliderDots");
      const prevBtn = slider.querySelector(".slider-nav.prev");
      const nextBtn = slider.querySelector(".slider-nav.next");

      let index = 0;
      let timer = null;
      const AUTOPLAY_MS = 3200;

      const dots = slides.map((_, i) => {
        const dot = document.createElement("button");
        dot.type = "button";
        dot.setAttribute("aria-label", `Go to slide ${i + 1}`);
        dot.addEventListener("click", () => goTo(i, true));
        if (dotsWrap) dotsWrap.appendChild(dot);
        return dot;
      });

      function render() {
        slides.forEach((s, i) =>
          s.classList.toggle("is-active", i === index)
        );
        dots.forEach((d, i) =>
          d.classList.toggle("is-active", i === index)
        );
      }

      function goTo(i, userAction = false) {
        index = (i + slides.length) % slides.length;
        render();
        if (userAction) restart();
      }

      function next() { goTo(index + 1); }
      function prev() { goTo(index - 1); }

      function start() {
        stop();
        timer = setInterval(next, AUTOPLAY_MS);
      }

      function stop() {
        if (timer) clearInterval(timer);
        timer = null;
      }

      function restart() {
        stop();
        start();
      }

      if (nextBtn) nextBtn.addEventListener("click", () => goTo(index + 1, true));
      if (prevBtn) prevBtn.addEventListener("click", () => goTo(index - 1, true));

      slider.addEventListener("mouseenter", stop);
      slider.addEventListener("mouseleave", start);

      let touchStartX = 0;

      slider.addEventListener("touchstart", (e) => {
        touchStartX = e.touches[0].clientX;
      }, { passive: true });

      slider.addEventListener("touchend", (e) => {
        const dx = e.changedTouches[0].clientX - touchStartX;
        if (Math.abs(dx) > 40) {
          dx > 0 ? goTo(index - 1, true) : goTo(index + 1, true);
        }
      }, { passive: true });

      render();
      start();
    }


    /* =====================================================
       COUNTERS
    ===================================================== */

    const counters = document.querySelectorAll("[data-counter]");

    if (counters.length) {

      const prefersReduced =
        window.matchMedia("(prefers-reduced-motion: reduce)").matches;

      const animateCounter = (el) => {
        const target = Number(el.getAttribute("data-target") || "0");

        if (!target || prefersReduced) {
          el.textContent = target.toLocaleString();
          return;
        }

        const duration = 1100;
        const startTime = performance.now();

        const step = (now) => {
          const progress = Math.min(1, (now - startTime) / duration);
          const eased = 1 - Math.pow(1 - progress, 3);
          const value = Math.round(target * eased);

          el.textContent = value.toLocaleString();

          if (progress < 1) requestAnimationFrame(step);
        };

        requestAnimationFrame(step);
      };

      const observer = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              animateCounter(entry.target);
              observer.unobserve(entry.target);
            }
          });
        },
        { threshold: 0.35 }
      );

      counters.forEach((counter) => observer.observe(counter));
    }

  });

})();