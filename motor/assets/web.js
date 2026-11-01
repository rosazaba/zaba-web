/* Zaba — interacción: menú, cabecera, aparición, visor de fotos y formulario */
(function () {
  document.documentElement.classList.add("js");
  var body = document.body;

  /* Menú móvil */
  var boton = document.querySelector("[data-hamburguesa]");
  if (boton) {
    boton.addEventListener("click", function () {
      var abierto = body.classList.toggle("menu-abierto");
      boton.setAttribute("aria-expanded", abierto);
    });
    document.querySelectorAll(".menu a").forEach(function (a) {
      a.addEventListener("click", function () { body.classList.remove("menu-abierto"); boton.setAttribute("aria-expanded", false); });
    });
  }

  /* Cabecera: fondo al hacer scroll */
  var cab = document.querySelector("[data-cabecera]");
  function alScroll() { if (cab) cab.classList.toggle("con-sombra", window.scrollY > 40); }
  window.addEventListener("scroll", alScroll, { passive: true });
  alScroll();

  /* Aparición suave */
  var elementos = document.querySelectorAll(".aparece");
  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (entradas) {
      entradas.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add("visible"); io.unobserve(e.target); } });
    }, { rootMargin: "0px 0px -8% 0px" });
    elementos.forEach(function (el) { io.observe(el); });
  } else {
    elementos.forEach(function (el) { el.classList.add("visible"); });
  }

  /* Visor de fotos */
  var galerias = document.querySelectorAll("[data-galeria]");
  if (galerias.length) {
    var visor = document.createElement("div");
    visor.className = "visor";
    visor.setAttribute("role", "dialog");
    visor.setAttribute("aria-modal", "true");
    visor.innerHTML = '<img alt=""><button class="visor__cerrar" aria-label="Close">×</button>' +
      '<button class="visor__ant" aria-label="Previous">‹</button><button class="visor__sig" aria-label="Next">›</button>' +
      '<div class="visor__contador"></div>';
    body.appendChild(visor);
    var img = visor.querySelector("img"), contador = visor.querySelector(".visor__contador");
    var lista = [], actual = 0, ultimoFoco = null;

    function mostrar(i) {
      actual = (i + lista.length) % lista.length;
      var a = lista[actual];
      img.style.opacity = 0;
      var nueva = new Image();
      nueva.onload = function () { img.src = a.href; img.alt = a.querySelector("img").alt; img.style.opacity = 1; };
      nueva.src = a.href;
      contador.textContent = (actual + 1) + " / " + lista.length;
      // precarga la siguiente
      var sig = lista[(actual + 1) % lista.length]; if (sig) (new Image()).src = sig.href;
    }
    function abrir(gal, i) {
      lista = Array.prototype.slice.call(gal.querySelectorAll("a"));
      ultimoFoco = document.activeElement;
      visor.classList.add("abierto"); body.style.overflow = "hidden";
      mostrar(i);
      visor.querySelector(".visor__cerrar").focus();
    }
    function cerrar() {
      visor.classList.remove("abierto"); body.style.overflow = ""; img.src = "";
      if (ultimoFoco) ultimoFoco.focus();
    }
    galerias.forEach(function (gal) {
      gal.querySelectorAll("a").forEach(function (a, i) {
        a.addEventListener("click", function (e) { e.preventDefault(); abrir(gal, i); });
      });
    });
    visor.querySelector(".visor__cerrar").onclick = cerrar;
    visor.querySelector(".visor__ant").onclick = function () { mostrar(actual - 1); };
    visor.querySelector(".visor__sig").onclick = function () { mostrar(actual + 1); };
    visor.addEventListener("click", function (e) { if (e.target === visor) cerrar(); });
    document.addEventListener("keydown", function (e) {
      if (!visor.classList.contains("abierto")) return;
      if (e.key === "Escape") cerrar();
      if (e.key === "ArrowLeft") mostrar(actual - 1);
      if (e.key === "ArrowRight") mostrar(actual + 1);
    });
    /* deslizar con el dedo */
    var x0 = null, y0 = null;
    visor.addEventListener("touchstart", function (e) { x0 = e.touches[0].clientX; y0 = e.touches[0].clientY; }, { passive: true });
    visor.addEventListener("touchend", function (e) {
      if (x0 === null) return;
      var dx = e.changedTouches[0].clientX - x0, dy = e.changedTouches[0].clientY - y0;
      if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy)) mostrar(actual + (dx < 0 ? 1 : -1));
      else if (dy > 90) cerrar();
      x0 = null;
    });
  }

  /* Formulario de contacto */
  var form = document.querySelector("[data-formulario]");
  if (form) {
    var param = new URLSearchParams(location.search).get("s");
    var sel = form.querySelector("[data-servicio]");
    if (param && sel && sel.querySelector('option[value="' + param + '"]')) sel.value = param;
    var estado = form.querySelector(".formulario__estado");

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var clave = form.dataset.clave, datos = new FormData(form);
      if (clave) {
        datos.append("access_key", clave);
        var btn = form.querySelector("button"); btn.disabled = true;
        fetch("https://api.web3forms.com/submit", { method: "POST", body: datos })
          .then(function (r) { return r.json(); })
          .then(function (r) { if (!r.success) throw 0; estado.textContent = form.dataset.gracias; form.reset(); })
          .catch(function () { estado.textContent = form.dataset.error; })
          .finally(function () { btn.disabled = false; });
      } else {
        // Sin clave: abre el correo del visitante con el mensaje ya escrito
        var interes = sel ? sel.options[sel.selectedIndex].text : "";
        var texto = datos.get("message") + "\n\n— " + datos.get("name") + " (" + interes + ")";
        location.href = "mailto:" + (form.dataset.email || "") + "?subject=" + encodeURIComponent(datos.get("subject") + " · " + interes) +
          "&body=" + encodeURIComponent(texto);
      }
    });
  }
})();
