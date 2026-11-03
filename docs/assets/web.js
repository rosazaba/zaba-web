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
      lista = Array.prototype.slice.call(gal.querySelectorAll("a:not([data-copia])"));
      i = i % lista.length;                 // las copias de la tira abren la foto original
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

  /* Tira de fotos de la portada: avanza sola, se para al tocarla o pasar el ratón y se puede deslizar */
  document.querySelectorAll("[data-tira]").forEach(function (visorTira) {
    var pista = visorTira.firstElementChild;
    var quieto = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    var pausa = false, reanudar = null, pos = 0, ultimo = null, VEL = 28;   // píxeles por segundo
    function mitad() { return pista.scrollWidth / 2; }
    function parar() { pausa = true; clearTimeout(reanudar); }
    function seguir(ms) { clearTimeout(reanudar); reanudar = setTimeout(function () { pausa = false; pos = visorTira.scrollLeft; }, ms); }
    visorTira.addEventListener("pointerenter", function (e) { if (e.pointerType === "mouse") parar(); });
    visorTira.addEventListener("pointerleave", function (e) { if (e.pointerType === "mouse") seguir(300); });
    visorTira.addEventListener("touchstart", parar, { passive: true });
    visorTira.addEventListener("touchend", function () { seguir(2500); }, { passive: true });
    visorTira.addEventListener("focusin", parar);
    visorTira.addEventListener("focusout", function () { seguir(1000); });
    visorTira.addEventListener("scroll", function () {
      var m = mitad();                      // bucle infinito: al pasar la mitad vuelve al principio
      if (visorTira.scrollLeft >= m) { visorTira.scrollLeft -= m; pos = visorTira.scrollLeft; }
      else if (visorTira.scrollLeft <= 0 && pausa) { visorTira.scrollLeft += m; pos = visorTira.scrollLeft; }
    }, { passive: true });
    var visible = true;
    if ("IntersectionObserver" in window) new IntersectionObserver(function (e) { visible = e[0].isIntersecting; }).observe(visorTira);
    function paso(t) {
      if (ultimo !== null && !pausa && visible && !quieto) {
        pos += VEL * Math.min(t - ultimo, 64) / 1000;
        if (pos >= mitad()) pos -= mitad();
        visorTira.scrollLeft = pos;
      }
      ultimo = t; requestAnimationFrame(paso);
    }
    requestAnimationFrame(paso);
  });

  /* Encuentra tus fotos: fichas por playa y buscador por texto (playa, pueblo, fecha) sobre las tarjetas de sesión */
  var buscador = document.querySelector("[data-buscador]");
  if (buscador) {
    var campo = buscador.querySelector("[data-buscar]");
    var fichas = buscador.querySelectorAll("[data-playa]");
    var playaActiva = "";
    var normal = function (t) { return (t || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, ""); };
    function filtrar() {
      var q = normal(campo.value.trim()), alguna = false;
      buscador.querySelectorAll("[data-tarjeta]").forEach(function (t) {
        var ok = (!playaActiva || t.dataset.playaDe === playaActiva) && (!q || normal(t.dataset.texto).indexOf(q) > -1);
        t.hidden = !ok; if (ok) alguna = true;
      });
      buscador.querySelector("[data-nada]").hidden = alguna;
    }
    campo.addEventListener("input", filtrar);
    fichas.forEach(function (f) {
      f.addEventListener("click", function () {
        playaActiva = f.dataset.playa;
        fichas.forEach(function (o) { o.setAttribute("aria-pressed", o === f); });
        filtrar();
      });
    });
  }

  /* Galerías con apartados (buceo): pestañas */
  document.querySelectorAll("[data-pestanas]").forEach(function (caja) {
    var botones = caja.querySelectorAll("[data-pestana]");
    if (!botones.length) return;
    function ver(id) {
      botones.forEach(function (b) { b.setAttribute("aria-selected", b.dataset.pestana === id); });
      caja.querySelectorAll("[data-panel]").forEach(function (p) { p.hidden = p.dataset.panel !== id; });
    }
    botones.forEach(function (b) { b.addEventListener("click", function () { ver(b.dataset.pestana); }); });
    ver(botones[0].dataset.pestana);
  });

  /* Tienda: pestañas por categoría, elegir foto (se apunta en el pedido) y pedido por WhatsApp */
  var elige = document.querySelector("[data-elige]");
  var pedido = document.querySelector("[data-pedido]");
  if (elige) {
    var pestanas = elige.querySelectorAll("[data-pestana]");
    function verGrupo(id) {
      pestanas.forEach(function (p) { p.setAttribute("aria-selected", p.dataset.pestana === id); });
      elige.querySelectorAll("[data-grupo]").forEach(function (gr) { gr.hidden = gr.dataset.grupo !== id; });
    }
    if (pestanas.length) {
      pestanas.forEach(function (p) { p.addEventListener("click", function () { verGrupo(p.dataset.pestana); }); });
      verGrupo(pestanas[0].dataset.pestana);
    }
    elige.querySelectorAll("[data-ver-mas]").forEach(function (b) {
      b.addEventListener("click", function () { b.closest("[data-grupo]").classList.add("abierto"); });
    });
    var campoFoto = pedido && pedido.querySelector("[data-foto-elegida]");
    elige.querySelectorAll("[data-codigo-foto]").forEach(function (b) {
      b.addEventListener("click", function () {
        elige.querySelectorAll("[data-codigo-foto]").forEach(function (o) { o.setAttribute("aria-pressed", o === b); });
        if (campoFoto) {
          campoFoto.value = b.dataset.codigoFoto;
          campoFoto.classList.add("recien-elegida");
          setTimeout(function () { campoFoto.classList.remove("recien-elegida"); }, 1600);
        }
      });
    });
  }
  if (pedido) {
    pedido.addEventListener("submit", function (e) {
      e.preventDefault();
      var lineas = [pedido.dataset.saludo];
      pedido.querySelectorAll("[data-etiqueta]").forEach(function (c) {
        var v = (c.tagName === "SELECT" ? (c.value ? c.options[c.selectedIndex].text : "") : c.value).trim();
        if (v) lineas.push(c.dataset.etiqueta + ": " + v);
      });
      window.open("https://wa.me/" + pedido.dataset.whatsapp + "?text=" + encodeURIComponent(lineas.join("\n")), "_blank", "noopener");
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
        var nombre = [datos.get("name"), datos.get("surname")].filter(Boolean).join(" ");
        var texto = datos.get("message") + "\n\n— " + nombre + " (" + interes + ")";
        var destino = form.dataset.destino ? atob(form.dataset.destino.split("").reverse().join("")) : "";
        location.href = "mailto:" + destino + "?subject=" + encodeURIComponent(datos.get("subject") + " · " + interes) +
          "&body=" + encodeURIComponent(texto);
      }
    });
  }
})();
