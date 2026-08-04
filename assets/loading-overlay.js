/* Overlay de carga compartido — logo con anillo girando mientras procesa,
   check verde al completar, luego se desvanece. Se inyecta una sola vez y
   se controla con window.mostrarCargando(mensaje) / completarCargando(). */
(function () {
  if (document.getElementById('loading-overlay')) return;

  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const style = document.createElement('style');
  style.textContent = `
#loading-overlay {
  position: fixed; inset: 0; z-index: 1000;
  display: flex; align-items: center; justify-content: center;
  background: rgba(5,5,7,.72); backdrop-filter: blur(3px);
  opacity: 0; pointer-events: none;
  transition: opacity ${reduceMotion ? '0ms' : '200ms'} ease-out;
}
#loading-overlay.visible { opacity: 1; pointer-events: auto; }
#loading-overlay .lo-box {
  display: flex; flex-direction: column; align-items: center; gap: 14px;
}
#loading-overlay .lo-ring-wrap { position: relative; width: 76px; height: 76px; }
#loading-overlay .lo-logo {
  position: absolute; inset: 8px; width: 60px; height: 60px;
  border-radius: 9999px; object-fit: cover;
}
#loading-overlay .lo-ring {
  position: absolute; inset: 0; border-radius: 9999px;
  border: 3px solid rgba(255,255,255,.12);
  border-top-color: var(--accent, #3956FA);
  animation: lo-spin ${reduceMotion ? '1600ms' : '900ms'} linear infinite;
}
#loading-overlay.done .lo-ring { display: none; }
#loading-overlay .lo-check {
  position: absolute; inset: 0; display: none; align-items: center; justify-content: center;
  border-radius: 9999px; background: #16a34a;
  transform: scale(.5); opacity: 0;
  transition: transform ${reduceMotion ? '0ms' : '250ms'} cubic-bezier(.34,1.56,.64,1), opacity ${reduceMotion ? '0ms' : '200ms'} ease-out;
}
#loading-overlay.done .lo-check { display: flex; transform: scale(1); opacity: 1; }
#loading-overlay .lo-msg {
  font-family: 'Fira Sans', system-ui, sans-serif; font-size: 13px; font-weight: 500;
  color: #ececf1; text-align: center; max-width: 260px;
}
@keyframes lo-spin { to { transform: rotate(360deg); } }
`;
  document.head.appendChild(style);

  const overlay = document.createElement('div');
  overlay.id = 'loading-overlay';
  overlay.innerHTML = `
    <div class="lo-box">
      <div class="lo-ring-wrap">
        <img class="lo-logo" src="/assets/andres-duque-logo.png" alt="">
        <div class="lo-ring"></div>
        <div class="lo-check">
          <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>
        </div>
      </div>
      <div class="lo-msg"></div>
    </div>`;
  document.body.appendChild(overlay);

  const msg = overlay.querySelector('.lo-msg');
  let hideTimer = null;

  window.mostrarCargando = function (mensaje) {
    clearTimeout(hideTimer);
    overlay.classList.remove('done');
    msg.textContent = mensaje || '';
    overlay.classList.add('visible');
  };

  window.completarCargando = function () {
    overlay.classList.add('done');
    hideTimer = setTimeout(() => {
      overlay.classList.remove('visible');
    }, reduceMotion ? 400 : 700);
  };

  window.cancelarCargando = function () {
    clearTimeout(hideTimer);
    overlay.classList.remove('visible', 'done');
  };
})();
