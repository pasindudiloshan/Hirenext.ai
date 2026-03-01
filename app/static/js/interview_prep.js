document.addEventListener("DOMContentLoaded", () => {
  const el = {
    btnClose: document.getElementById("btnClose"),
    btnCancel: document.getElementById("btnCancel"),
    btnJoin: document.getElementById("btnJoin"),

    btnCam: document.getElementById("btnCam"),
    btnMic: document.getElementById("btnMic"),
    camSwitch: document.getElementById("camSwitch"),
    micSwitch: document.getElementById("micSwitch"),
    camBadge: document.getElementById("camBadge"),

    audioRows: Array.from(document.querySelectorAll(".lp-row[data-audio]")),
  };

  const state = {
    camOn: true,
    micOn: true,
    audioMode: "computer",
  };

  function setCam(on){
    state.camOn = on;
    el.btnCam.setAttribute("aria-pressed", String(on));
    el.camSwitch.classList.toggle("on", on);
    el.camBadge.textContent = on ? "Camera On" : "Camera Off";
  }

  function setMic(on){
    state.micOn = on;
    el.btnMic.setAttribute("aria-pressed", String(on));
    el.micSwitch.classList.toggle("on", on);
  }

  function setAudio(mode){
    state.audioMode = mode;

    el.audioRows.forEach(row => {
      const active = row.dataset.audio === mode;
      row.classList.toggle("selected", active);

      const right = row.querySelector(".lp-row-right");
      if (!right) return;

      right.innerHTML = active
        ? `<span class="lp-check"><i class="fa-solid fa-check"></i></span>`
        : `<span class="lp-radio"></span>`;
    });
  }

  // wiring
  el.btnCam?.addEventListener("click", () => setCam(!state.camOn));
  el.btnMic?.addEventListener("click", () => setMic(!state.micOn));

  el.audioRows.forEach(row => {
    row.addEventListener("click", () => setAudio(row.dataset.audio));
  });

  function closePopup(){
    // If opened as a real popup window:
    // window.close();

    // If opened as a normal page route:
    history.back();
  }

  el.btnClose?.addEventListener("click", closePopup);
  el.btnCancel?.addEventListener("click", closePopup);

  el.btnJoin?.addEventListener("click", () => {
    // Change this route to your real join URL:
    // window.location.href = "/interview/session";
    alert("Joining now (demo)...");
  });

  // init
  setCam(true);
  setMic(true);
  setAudio("computer");
});