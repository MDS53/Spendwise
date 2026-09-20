/* =====================================================================
   Spendwise – shared UI helpers  (window.SW)
   Load this in <head> (after api.js) so the theme applies before paint.
   ===================================================================== */
(function (w, d) {
  'use strict';

  var CURRENCY = 'USD';      // change to 'INR', 'EUR', 'CHF' ... to change every amount
  var LOCALE = 'en-US';      // e.g. 'en-IN' for Indian digit grouping

  var reduce = w.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var fmt = new Intl.NumberFormat(LOCALE, { style: 'currency', currency: CURRENCY });
  var symbol = fmt.formatToParts(0).filter(function (p) { return p.type === 'currency'; })[0].value;

  /* ---------- Theme (applied immediately) ---------- */
  var saved = null;
  try { saved = localStorage.getItem('sw-theme'); } catch (e) {}
  d.documentElement.setAttribute('data-theme', saved || (w.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'));

  var toastEl, toastTimer;

  var SW = {
    reduce: reduce,
    symbol: symbol,
    money: function (n) { return fmt.format(n); },
    cap: function (s) { s = String(s || ''); return s.charAt(0).toUpperCase() + s.slice(1); },
    esc: function (s) {
      return String(s).replace(/[&<>"']/g, function (c) {
        return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
      });
    },
    initials: function (name) {
      var parts = String(name || '?').trim().split(/\s+/);
      return (parts[0].charAt(0) + (parts.length > 1 ? parts[parts.length - 1].charAt(0) : '')).toUpperCase();
    },

    toggleTheme: function () {
      var next = d.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      d.documentElement.setAttribute('data-theme', next);
      try { localStorage.setItem('sw-theme', next); } catch (e) {}
    },

    toast: function (msg) {
      if (!toastEl) {
        toastEl = d.createElement('div');
        toastEl.className = 'toast';
        toastEl.setAttribute('role', 'status');
        toastEl.setAttribute('aria-live', 'polite');
        d.body.appendChild(toastEl);
      }
      toastEl.textContent = msg;
      toastEl.classList.add('show');
      clearTimeout(toastTimer);
      toastTimer = setTimeout(function () { toastEl.classList.remove('show'); }, 2800);
    },

    /* Use on pages that need a logged-in user. Resolves with the user, or redirects to login. */
    requireLogin: function () {
      return w.SWApi.me().then(function (u) {
        if (!u) { w.location.replace('login.html'); return new Promise(function () {}); }
        return u;
      });
    },

    /* Tilt `target` (via --rx / --ry) while the pointer moves over `area`. */
    tilt: function (area, target, cfg) {
      if (reduce) return;
      cfg = cfg || {};
      var baseY = cfg.baseY == null ? 0 : cfg.baseY, baseX = cfg.baseX == null ? 0 : cfg.baseX;
      var rangeY = cfg.rangeY || 22, rangeX = cfg.rangeX || 14;
      target.style.setProperty('--ry', baseY + 'deg');
      target.style.setProperty('--rx', baseX + 'deg');
      area.addEventListener('pointermove', function (e) {
        if (e.pointerType === 'touch') return;
        var r = area.getBoundingClientRect();
        var px = (e.clientX - r.left) / r.width - .5, py = (e.clientY - r.top) / r.height - .5;
        target.style.setProperty('--ry', (baseY + px * rangeY).toFixed(2) + 'deg');
        target.style.setProperty('--rx', (baseX - py * rangeX).toFixed(2) + 'deg');
        var bankEl = target.querySelector('.bank');
        if (bankEl) {
          bankEl.style.setProperty('--mouse-x', Math.round((e.clientX - r.left) / r.width * 100) + '%');
          bankEl.style.setProperty('--mouse-y', Math.round((e.clientY - r.top) / r.height * 100) + '%');
        }
      });
      area.addEventListener('pointerleave', function () {
        target.style.setProperty('--ry', baseY + 'deg');
        target.style.setProperty('--rx', baseX + 'deg');
      });
    },

    /* Animate a number inside `el` from 0 to `to` as money. */
    countUp: function (el, to, ms) {
      if (reduce) { el.textContent = SW.money(to); return; }
      var start = null; ms = ms || 900;
      function step(t) {
        if (start === null) start = t;
        var p = Math.min(1, (t - start) / ms), e = 1 - Math.pow(1 - p, 3);
        el.textContent = SW.money(to * e);
        if (p < 1) requestAnimationFrame(step); else el.textContent = SW.money(to);
      }
      requestAnimationFrame(step);
    },

    /* Full-screen confetti burst. */
    confetti: function () {
      if (reduce) return;
      var c = d.createElement('canvas');
      c.className = 'confetti';
      c.setAttribute('aria-hidden', 'true');
      d.body.appendChild(c);
      var W = c.width = w.innerWidth, H = c.height = w.innerHeight, ctx = c.getContext('2d');
      var colors = ['#5A46FF', '#1FCB93', '#FFC93C', '#FF6474', '#FFFFFF'];
      var bits = [];
      for (var i = 0; i < 150; i++) {
        var a = -Math.PI / 2 + (Math.random() - .5) * 1.6, s = 7 + Math.random() * 10;
        bits.push({
          x: W / 2, y: H * .42, vx: Math.cos(a) * s, vy: Math.sin(a) * s,
          w: 6 + Math.random() * 7, h: 4 + Math.random() * 6, r: Math.random() * 6, vr: (Math.random() - .5) * .35,
          c: colors[i % colors.length]
        });
      }
      var t0 = performance.now();
      (function frame(now) {
        var age = now - t0;
        ctx.clearRect(0, 0, W, H);
        bits.forEach(function (b) {
          b.vy += .28; b.vx *= .992; b.x += b.vx; b.y += b.vy; b.r += b.vr;
          ctx.save();
          ctx.globalAlpha = Math.max(0, 1 - age / 3000);
          ctx.translate(b.x, b.y); ctx.rotate(b.r);
          ctx.fillStyle = b.c; ctx.fillRect(-b.w / 2, -b.h / 2, b.w, b.h);
          ctx.restore();
        });
        if (age < 3000) requestAnimationFrame(frame); else c.remove();
      })(t0);
    },

    /* The 3D bank card used on the login + signup pages. */
    artCard: function (host) {
      host.innerHTML =
        '<div class="card-3d">' +
          '<div class="card-layer" style="--z:0px;left:0;top:0">' +
            '<div class="bank">' +
              '<div class="bank-top"><span class="mark">$</span>Spendwise</div>' +
              '<div class="bank-bal"><small>Available to spend</small><strong>' + SW.money(1980) + '</strong></div>' +
              '<div class="bank-foot"><span>•••• 2648</span><span>Alex Morgan</span></div>' +
            '</div>' +
          '</div>' +
          '<div class="card-layer" style="--z:85px;right:-44px;top:-30px"><div class="float"><div class="chip">Daily limit <b>' + SW.money(60) + '</b></div></div></div>' +
          '<div class="card-layer" style="--z:60px;left:-40px;bottom:-26px"><div class="float" style="--d:-2s"><div class="chip">Buffer kept <b>' + SW.money(500) + '</b></div></div></div>' +
          '<div class="card-layer" style="--z:100px;right:-20px;bottom:-35px"><div class="float" style="--d:-3.5s"><div class="chip" style="background:var(--sun);color:#2B2000;font-weight:800">⚡ Instant Check</div></div></div>' +
        '</div>';
      SW.tilt(host.closest('.auth-art') || host, host.firstChild, { baseY: -14, baseX: 8, rangeY: 26, rangeX: 16 });
    }
  };

  w.SW = SW;

  /* ---------- Wire up common controls once the page is ready ---------- */
  d.addEventListener('DOMContentLoaded', function () {
    d.querySelectorAll('[data-theme-toggle]').forEach(function (b) { b.addEventListener('click', SW.toggleTheme); });
    d.querySelectorAll('[data-cur]').forEach(function (el) { el.textContent = symbol; });
    d.querySelectorAll('[data-art]').forEach(SW.artCard);

    d.querySelectorAll('[data-logout]').forEach(function (b) {
      b.addEventListener('click', function (e) {
        e.preventDefault();
        w.SWApi.logout().then(function () { w.location.href = 'index.html'; });
      });
    });

    d.querySelectorAll('[data-pw-toggle]').forEach(function (b) {
      b.addEventListener('click', function () {
        var input = b.parentNode.querySelector('input');
        var show = input.type === 'password';
        input.type = show ? 'text' : 'password';
        b.textContent = show ? 'Hide' : 'Show';
        b.setAttribute('aria-pressed', String(show));
      });
    });
  });
})(window, document);
