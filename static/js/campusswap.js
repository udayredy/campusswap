/* CampusSwap – small progressive enhancements. Every feature also works without JS. */
(function () {
  "use strict";

  function getCookie(name) {
    const m = document.cookie.match("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)");
    return m ? decodeURIComponent(m.pop()) : "";
  }

  // ---- Favourite hearts: toggle without a page reload ----
  document.addEventListener("submit", function (e) {
    const form = e.target.closest("form.js-fav");
    if (!form) return;
    e.preventDefault();
    const btn = form.querySelector("button");
    btn.disabled = true;
    fetch(form.action, {
      method: "POST",
      headers: { "X-CSRFToken": getCookie("csrftoken") || form.querySelector("[name=csrfmiddlewaretoken]").value, "X-Requested-With": "XMLHttpRequest" },
      credentials: "same-origin",
    })
      .then(function (r) { return r.json().then(function (d) { return { status: r.status, data: d }; }); })
      .then(function (res) {
        if (res.status === 401 && res.data.login_url) { window.location = res.data.login_url; return; }
        const saved = res.data.saved;
        document.querySelectorAll('form.js-fav[action="' + form.getAttribute("action") + '"]').forEach(function (f) {
          const b = f.querySelector("button");
          const icon = b.querySelector(".bi");
          icon.className = "bi " + (saved ? "bi-heart-fill" : "bi-heart");
          b.setAttribute("aria-pressed", saved ? "true" : "false");
          b.setAttribute("title", saved ? "Remove from favourites" : "Save to favourites");
          const lbl = b.querySelector(".fav-label");
          if (lbl) lbl.textContent = saved ? "Saved" : "Save";
        });
        const badge = document.getElementById("fav-count");
        if (badge && typeof res.data.count === "number") {
          badge.textContent = res.data.count;
          badge.classList.toggle("d-none", res.data.count === 0);
        }
      })
      .catch(function () { form.submit(); })
      .finally(function () { btn.disabled = false; });
  });

  // ---- Listing gallery thumbnails ----
  document.querySelectorAll("[data-gallery]").forEach(function (g) {
    const main = g.querySelector(".gallery-main img");
    g.querySelectorAll(".gallery-thumbs button").forEach(function (b) {
      b.addEventListener("click", function () {
        main.src = b.dataset.src;
        g.querySelectorAll(".gallery-thumbs button").forEach(function (x) { x.classList.remove("active"); });
        b.classList.add("active");
      });
    });
  });

  // ---- Photo picker: drag & drop + previews + client-side limit ----
  document.querySelectorAll("[data-dropzone]").forEach(function (zone) {
    const input = zone.querySelector("input[type=file]");
    const grid = document.getElementById(zone.dataset.preview);
    const msg = document.getElementById(zone.dataset.msg);
    const max = parseInt(zone.dataset.max || "5", 10);
    const maxMb = parseInt(zone.dataset.maxmb || "5", 10);
    zone.addEventListener("click", function (e) { if (e.target !== input) input.click(); });
    zone.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.click(); } });
    ["dragenter", "dragover"].forEach(function (ev) { zone.addEventListener(ev, function (e) { e.preventDefault(); zone.classList.add("drag"); }); });
    ["dragleave", "drop"].forEach(function (ev) { zone.addEventListener(ev, function (e) { e.preventDefault(); zone.classList.remove("drag"); }); });
    zone.addEventListener("drop", function (e) { input.files = e.dataTransfer.files; input.dispatchEvent(new Event("change")); });
    input.addEventListener("change", function () {
      grid.innerHTML = "";
      msg.textContent = "";
      msg.className = "small mt-2";
      const files = Array.from(input.files);
      if (files.length > max) { msg.textContent = "You picked " + files.length + " photos – only " + max + " allowed here. Please choose fewer."; msg.classList.add("text-danger"); }
      files.forEach(function (f) {
        if (f.size > maxMb * 1024 * 1024) { msg.textContent = "“" + f.name + "” is over " + maxMb + " MB."; msg.classList.add("text-danger"); }
        if (!f.type.startsWith("image/")) return;
        const img = document.createElement("img");
        img.alt = f.name;
        img.src = URL.createObjectURL(f);
        grid.appendChild(img);
      });
      if (!msg.textContent && files.length) { msg.textContent = files.length + " photo" + (files.length > 1 ? "s" : "") + " ready to upload."; msg.classList.add("text-success"); }
    });
  });

  // ---- Password strength hint on sign-up ----
  const pw = document.getElementById("id_password1");
  const meter = document.getElementById("pw-meter");
  if (pw && meter) {
    const bar = meter.querySelector("span");
    const label = document.getElementById("pw-label");
    pw.addEventListener("input", function () {
      const v = pw.value;
      let s = 0;
      if (v.length >= 8) s++;
      if (v.length >= 12) s++;
      if (/[A-Z]/.test(v) && /[a-z]/.test(v)) s++;
      if (/\d/.test(v)) s++;
      if (/[^A-Za-z0-9]/.test(v)) s++;
      if (/^\d+$/.test(v)) s = Math.min(s, 1);
      const levels = [["0%", "#eceef2", ""], ["25%", "#d64545", "Too weak"], ["45%", "#e67e22", "Weak"], ["65%", "#f5a623", "Okay"], ["85%", "#2e9e5b", "Strong"], ["100%", "#1f7a46", "Very strong"]];
      const lv = v ? levels[Math.max(1, s)] : levels[0];
      bar.style.width = lv[0]; bar.style.background = lv[1]; label.textContent = lv[2];
    });
  }

  // ---- Show/hide password toggles ----
  document.querySelectorAll("[data-toggle-pw]").forEach(function (b) {
    b.addEventListener("click", function () {
      const input = document.getElementById(b.dataset.togglePw);
      const show = input.type === "password";
      input.type = show ? "text" : "password";
      b.querySelector(".bi").className = "bi " + (show ? "bi-eye-slash" : "bi-eye");
      b.setAttribute("aria-label", show ? "Hide password" : "Show password");
    });
  });

  // ---- Prevent double submits ----
  document.querySelectorAll("form[data-once]").forEach(function (f) {
    f.addEventListener("submit", function () {
      const b = f.querySelector("[type=submit]");
      if (b) { setTimeout(function () { b.disabled = true; b.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Working…'; }, 0); }
    });
  });

  // ---- Scroll chat to the latest message ----
  const chat = document.querySelector(".chat");
  if (chat) chat.scrollTop = chat.scrollHeight;

  // ---- Auto-dismiss success toasts ----
  document.querySelectorAll(".toast-stack .alert-success").forEach(function (a) {
    setTimeout(function () { if (window.bootstrap) bootstrap.Alert.getOrCreateInstance(a).close(); }, 5000);
  });
})();
