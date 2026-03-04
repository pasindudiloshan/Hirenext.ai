/* static/js/interview_results.js
   - Progress ring animates 0 -> finalScore/10
   - Download PDF (client-side) using print dialog OR html2pdf if you add it
*/

document.addEventListener("DOMContentLoaded", () => {
  const ring = document.querySelector(".ir-ring");
  const fg = document.querySelector(".ir-ring-fg");
  const num = document.getElementById("irScoreNum");

  // ------- Ring animation -------
  if (ring && fg && num) {
    const score = Number(ring.dataset.score || 0);
    const max = Number(ring.dataset.max || 10);

    // SVG circle circumference: 2πr (r=46 from HTML)
    const r = 46;
    const C = 2 * Math.PI * r;

    fg.style.strokeDasharray = String(C);
    fg.style.strokeDashoffset = String(C);

    const clamped = Math.max(0, Math.min(score, max));
    const targetPct = clamped / max; // 0..1
    const targetOffset = C * (1 - targetPct);

    // animate: 0 -> target over 900ms
    const duration = 900;
    const start = performance.now();

    function easeOutCubic(t) {
      return 1 - Math.pow(1 - t, 3);
    }

    function tick(now) {
      const t = Math.min(1, (now - start) / duration);
      const e = easeOutCubic(t);

      const currentOffset = C - (C - targetOffset) * e;
      fg.style.strokeDashoffset = String(currentOffset);

      const currentScore = (clamped * e);
      num.textContent = currentScore.toFixed(1);

      if (t < 1) requestAnimationFrame(tick);
      else num.textContent = clamped.toFixed(1);
    }

    requestAnimationFrame(tick);
  }

  // ------- Download PDF -------
  const btnPdf = document.getElementById("btnDownloadPdf");
  if (btnPdf) {
    btnPdf.addEventListener("click", () => {
      // Simple, no-dependency approach:
      // Open browser print dialog; user can Save as PDF.
      // If you want true 1-click PDF, I can give an html2pdf.js version too.
      window.print();
    });
  }
});