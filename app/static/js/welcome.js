/* =========================
   HireNext Welcome Page JS
   - 4 image autoplay slider
   - animated counters
========================= */

(function () {
  // ---------- Slider ----------
  const slider = document.getElementById("hnSlider");
  if (slider) {
    const slides = Array.from(slider.querySelectorAll(".slide"));
    const dotsWrap = document.getElementById("hnSliderDots");
    const prevBtn = slider.querySelector(".slider-nav.prev");
    const nextBtn = slider.querySelector(".slider-nav.next");

    let index = 0;
    let timer = null;
    const AUTOPLAY_MS = 3200;

    // Build dots
    const dots = slides.map((_, i) => {
      const b = document.createElement("button");
      b.type = "button";
      b.setAttribute("aria-label", `Go to slide ${i + 1}`);
      b.addEventListener("click", () => goTo(i, true));
      dotsWrap && dotsWrap.appendChild(b);
      return b;
    });

    function render() {
      slides.forEach((s, i) => s.classList.toggle("is-active", i === index));
      dots.forEach((d, i) => d.classList.toggle("is-active", i === index));
    }

    function goTo(i, userAction = false) {
      index = (i + slides.length) % slides.length;
      render();
      if (userAction) restart();
    }

    function next() { goTo(index + 1); }
    function prev() { goTo(index - 1); }

    function start() {
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

    // Buttons
    nextBtn && nextBtn.addEventListener("click", () => goTo(index + 1, true));
    prevBtn && prevBtn.addEventListener("click", () => goTo(index - 1, true));

    // Pause on hover (desktop)
    slider.addEventListener("mouseenter", stop);
    slider.addEventListener("mouseleave", start);

    // Touch swipe (mobile)
    let touchStartX = 0;
    slider.addEventListener("touchstart", (e) => {
      touchStartX = e.touches[0].clientX;
    }, { passive: true });

    slider.addEventListener("touchend", (e) => {
      const endX = e.changedTouches[0].clientX;
      const dx = endX - touchStartX;
      if (Math.abs(dx) > 40) {
        dx > 0 ? goTo(index - 1, true) : goTo(index + 1, true);
      }
    }, { passive: true });

    // Init
    render();
    start();
  }

  // ---------- Counters ----------
  const counters = document.querySelectorAll("[data-counter]");
  if (counters.length) {
    const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const animateCounter = (el) => {
      const target = Number(el.getAttribute("data-target") || "0");
      if (!target || prefersReduced) {
        el.textContent = target.toLocaleString();
        return;
      }

      const duration = 1100; // ms
      const start = 0;
      const startTime = performance.now();

      const step = (now) => {
        const t = Math.min(1, (now - startTime) / duration);
        const eased = 1 - Math.pow(1 - t, 3); // easeOutCubic
        const value = Math.round(start + (target - start) * eased);
        el.textContent = value.toLocaleString();

        if (t < 1) requestAnimationFrame(step);
      };

      requestAnimationFrame(step);
    };

    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            animateCounter(entry.target);
            io.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.35 }
    );

    counters.forEach((c) => io.observe(c));
  }
})();