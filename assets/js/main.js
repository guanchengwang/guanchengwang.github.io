/* ===========================================================================
   Guancheng Wang — site behaviour (shared by index.html and publications.html)
   Publication lists are server-rendered into the pages by
   scripts/update_publications.py, so everything here is progressive
   enhancement: with JS disabled the pages are still complete and readable.
   The one exception is the email address, which is deliberately assembled at
   runtime to keep it out of the served HTML.
   =========================================================================== */

(function () {
  'use strict';

  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ------------------------------------------------------------- theme */
  const root = document.documentElement;
  const STORAGE_KEY = 'gw-theme';

  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored) {
    root.setAttribute('data-theme', stored);
  } else if (window.matchMedia('(prefers-color-scheme: light)').matches) {
    root.setAttribute('data-theme', 'light');
  }

  const toggle = document.getElementById('themeToggle');
  if (toggle) {
    toggle.addEventListener('click', function () {
      const next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      root.setAttribute('data-theme', next);
      localStorage.setItem(STORAGE_KEY, next);
    });
  }

  /* -------------------------------------------------------------- nav */
  const nav = document.getElementById('nav');
  const burger = document.getElementById('navBurger');
  const links = document.querySelector('.nav__links');

  if (burger && links) {
    burger.addEventListener('click', function () {
      const open = links.classList.toggle('is-open');
      burger.setAttribute('aria-expanded', String(open));
    });
    links.addEventListener('click', function (e) {
      if (e.target.tagName === 'A') {
        links.classList.remove('is-open');
        burger.setAttribute('aria-expanded', 'false');
      }
    });
  }

  let ticking = false;
  window.addEventListener('scroll', function () {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(function () {
      if (nav) nav.classList.toggle('is-stuck', window.scrollY > 8);
      ticking = false;
    });
  }, { passive: true });

  /* Highlight the section currently in view. Only same-page anchors qualify —
     cross-page links like "publications.html" are not valid selectors and
     would throw. */
  const navAnchors = Array.from(document.querySelectorAll('.nav__links a'))
    .filter(function (a) {
      const href = a.getAttribute('href') || '';
      return href.charAt(0) === '#' && href.length > 1;
    });
  const sections = navAnchors
    .map(function (a) { return document.querySelector(a.getAttribute('href')); })
    .filter(Boolean);

  if (sections.length && 'IntersectionObserver' in window) {
    const spy = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        navAnchors.forEach(function (a) {
          a.classList.toggle('is-active', a.getAttribute('href') === '#' + entry.target.id);
        });
      });
    }, { rootMargin: '-45% 0px -50% 0px' });
    sections.forEach(function (s) { spy.observe(s); });
  }

  /* ---------------------------------------------------- scroll reveal */
  const revealables = document.querySelectorAll('.reveal');
  if ('IntersectionObserver' in window && !reduceMotion) {
    const io = new IntersectionObserver(function (entries, obs) {
      entries.forEach(function (entry, i) {
        if (!entry.isIntersecting) return;
        // Stagger siblings slightly so grids cascade instead of popping.
        entry.target.style.transitionDelay = Math.min(i * 60, 300) + 'ms';
        entry.target.classList.add('is-in');
        obs.unobserve(entry.target);
      });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.06 });
    revealables.forEach(function (el) { io.observe(el); });
  } else {
    revealables.forEach(function (el) { el.classList.add('is-in'); });
  }

  /* ------------------------------------------- publication filtering */
  const publist = document.getElementById('publist');
  const search = document.getElementById('pubSearch');
  const chips = Array.from(document.querySelectorAll('.chip[data-filter]'));
  const none = document.getElementById('pubNone');

  if (publist) {
    const pubs = Array.from(publist.querySelectorAll('.pub'));
    const headings = Array.from(publist.querySelectorAll('.pub-year-heading'));
    let activeType = 'all';

    function haystack(pub) {
      return (pub.dataset.title + ' ' + pub.dataset.authors + ' ' +
              pub.dataset.venue + ' ' + pub.dataset.topics + ' ' +
              pub.dataset.year).toLowerCase();
    }

    function apply() {
      const q = (search ? search.value : '').trim().toLowerCase();
      let visible = 0;

      pubs.forEach(function (pub) {
        const typeOk = activeType === 'all' || pub.dataset.type === activeType;
        const textOk = !q || haystack(pub).indexOf(q) !== -1;
        const show = typeOk && textOk;
        pub.hidden = !show;
        if (show) visible++;
      });

      // A year heading is only meaningful when something under it survived.
      headings.forEach(function (h) {
        let sib = h.nextElementSibling;
        let any = false;
        while (sib && !sib.classList.contains('pub-year-heading')) {
          if (sib.classList.contains('pub') && !sib.hidden) { any = true; break; }
          sib = sib.nextElementSibling;
        }
        h.hidden = !any;
      });

      if (none) none.hidden = visible !== 0;
    }

    chips.forEach(function (chip) {
      chip.addEventListener('click', function () {
        chips.forEach(function (c) { c.classList.remove('is-active'); });
        chip.classList.add('is-active');
        activeType = chip.dataset.filter;
        apply();
      });
    });

    if (search) {
      let t;
      search.addEventListener('input', function () {
        clearTimeout(t);
        t = setTimeout(apply, 120);
      });
    }
  }

  /* ------------------------------------------------------ mailto */
  // No mailto: link anywhere on this site, by design. A mailto: is a one-click
  // target for automated mail and puts the address in the DOM as soon as it is
  // wired up. Instead the address is stored as reversed base64, decoded only
  // when a visitor asks for it, and then offered as plain text to copy.
  var box = document.querySelector('.mailbox');
  var revealBtn = box && box.querySelector('.js-mail-reveal');
  if (box && revealBtn) {
    revealBtn.addEventListener('click', function () {
      var addr;
      try {
        addr = atob((box.getAttribute('data-e') || '').split('').reverse().join(''));
      } catch (e) {
        return;                     // malformed token: leave the button alone
      }

      var code = document.createElement('code');
      code.className = 'mailbox__addr';
      code.textContent = addr;

      var copy = document.createElement('button');
      copy.type = 'button';
      copy.className = 'mailbox__copy';
      copy.textContent = 'Copy';

      var flash = function (msg) {
        copy.textContent = msg;
        setTimeout(function () { copy.textContent = 'Copy'; }, 1800);
      };

      // Selecting the text is the fallback: navigator.clipboard needs a secure
      // context, so it is unavailable over plain http and in some embeds.
      var selectInstead = function () {
        var range = document.createRange();
        range.selectNodeContents(code);
        var sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
        var mac = /Mac|iPhone|iPad|iPod/.test(navigator.platform || navigator.userAgent);
        flash('Selected — press ' + (mac ? '⌘C' : 'Ctrl+C'));
      };

      copy.addEventListener('click', function () {
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(addr).then(function () { flash('Copied'); },
                                                   selectInstead);
        } else {
          selectInstead();
        }
      });

      box.replaceChild(code, revealBtn);
      box.appendChild(copy);
    });
  }

  /* ---------------------------------------------------- travel map */
  // Hovering either a list entry or a map pin highlights the other, so a long
  // list stays navigable without hunting for the matching dot.
  var pins = document.querySelectorAll('.map__pin[data-place]');
  var placeRows = document.querySelectorAll('.place[data-place]');

  if (pins.length && placeRows.length) {
    var byId = {};
    Array.prototype.forEach.call(pins, function (pin) {
      byId[pin.getAttribute('data-place')] = pin;
    });

    Array.prototype.forEach.call(placeRows, function (row) {
      var pin = byId[row.getAttribute('data-place')];
      if (!pin) return;
      var on = function () { pin.classList.add('is-active'); row.classList.add('is-active'); };
      var off = function () { pin.classList.remove('is-active'); row.classList.remove('is-active'); };
      row.addEventListener('mouseenter', on);
      row.addEventListener('mouseleave', off);
      pin.addEventListener('mouseenter', on);
      pin.addEventListener('mouseleave', off);
      pin.addEventListener('focus', on);
      pin.addEventListener('blur', off);
    });
  }

  /* ------------------------------------------------- map pan + zoom */
  // Ireland is a few pixels wide at world scale, so Limerick, Dublin, Cork and
  // Galway collapse into one blob. Zooming separates them.
  //
  // Everything is scoped to the frame: a plain wheel still scrolls the page
  // (zoom needs ctrl/⌘), and touch keeps `touch-action: pan-y` so the page can
  // still be scrolled with a finger on the map. Nothing here traps the reader.
  var mapSvg = document.querySelector('.map__svg');
  if (mapSvg) {
    var vb = (mapSvg.getAttribute('viewBox') || '').split(/\s+/).map(Number);
    var base = { x: vb[0], y: vb[1], w: vb[2], h: vb[3] };
    var view = { x: base.x, y: base.y, w: base.w, h: base.h };
    var MIN_W = base.w / 16;                    // deepest zoom
    var mapPins = mapSvg.querySelectorAll('.map__pin');
    var resetBtn = document.querySelector('.map__btn--reset');

    var applyView = function () {
      view.w = Math.min(base.w, Math.max(MIN_W, view.w));
      view.h = view.w * base.h / base.w;
      // Keep the frame full of map — never pan into empty space.
      view.x = Math.min(base.x + base.w - view.w, Math.max(base.x, view.x));
      view.y = Math.min(base.y + base.h - view.h, Math.max(base.y, view.y));
      mapSvg.setAttribute('viewBox',
        view.x.toFixed(2) + ' ' + view.y.toFixed(2) + ' ' +
        view.w.toFixed(2) + ' ' + view.h.toFixed(2));

      // Counter-scale the pins so dots and labels stay a constant size on
      // screen. This is what actually separates the cluster: positions spread
      // apart while the markers themselves do not grow.
      var inv = view.w / base.w;
      Array.prototype.forEach.call(mapPins, function (pin) {
        pin.setAttribute('transform',
          'translate(' + pin.dataset.x + ' ' + pin.dataset.y + ') scale(' + inv + ')');
      });
      if (resetBtn) resetBtn.disabled = view.w >= base.w - 0.01;
      updateLabels();
    };

    // Reveal place names once zoomed in far enough for them to be readable,
    // and only where they do not collide. Labels counter-scale with the pins,
    // so their size on screen is constant and the boxes can be measured in
    // screen pixels — no getBBox needed, which keeps this cheap during a drag.
    var LABEL_ZOOM = 2.2;
    var CHAR_W = 6.1, PAD = 10, HALF_H = 7;

    var labelOrder = Array.prototype.slice.call(mapPins).sort(function (a, b) {
      // The work pin claims its space first; everything else in list order.
      var aw = a.classList.contains('map__pin--work') ? 0 : 1;
      var bw = b.classList.contains('map__pin--work') ? 0 : 1;
      return aw - bw || (+a.dataset.place) - (+b.dataset.place);
    });

    function updateLabels() {
      var rect = mapSvg.getBoundingClientRect();
      if (!rect.width) return;
      var zoomed = (base.w / view.w) >= LABEL_ZOOM;
      var placed = [];

      labelOrder.forEach(function (pin) {
        var lbl = pin.querySelector('.map__label');
        if (!lbl) return;
        var isWork = pin.classList.contains('map__pin--work');

        var sx = (pin.dataset.x - view.x) / view.w * rect.width;
        var sy = (pin.dataset.y - view.y) / view.h * rect.height;
        var offscreen = sx < -40 || sy < -40 ||
                        sx > rect.width + 40 || sy > rect.height + 40;

        if (offscreen || (!zoomed && !isWork)) {
          lbl.classList.remove('is-shown');
          return;
        }

        var box = {
          l: sx + PAD - 2, t: sy - HALF_H,
          r: sx + PAD + lbl.textContent.length * CHAR_W, b: sy + HALF_H
        };
        var clash = placed.some(function (o) {
          return !(box.r < o.l || box.l > o.r || box.b < o.t || box.t > o.b);
        });

        // The work label is never suppressed; it reserves its box regardless.
        if (clash && !isWork) {
          lbl.classList.remove('is-shown');
          return;
        }
        placed.push(box);
        lbl.classList.add('is-shown');
      });
    }

    // Zoom about a fixed point, given in viewBox coordinates.
    var zoomAt = function (factor, cx, cy) {
      var nw = Math.min(base.w, Math.max(MIN_W, view.w / factor));
      var k = view.w / nw;
      view.x = cx - (cx - view.x) / k;
      view.y = cy - (cy - view.y) / k;
      view.w = nw;
      applyView();
    };

    var toView = function (clientX, clientY) {
      var r = mapSvg.getBoundingClientRect();
      return {
        x: view.x + (clientX - r.left) / r.width * view.w,
        y: view.y + (clientY - r.top) / r.height * view.h
      };
    };

    var centre = function () {
      return { x: view.x + view.w / 2, y: view.y + view.h / 2 };
    };

    /* drag to pan */
    var dragging = false, last = null, moved = 0;
    mapSvg.addEventListener('pointerdown', function (e) {
      if (e.button !== 0 && e.pointerType === 'mouse') return;
      dragging = true; moved = 0;
      last = { x: e.clientX, y: e.clientY };
      mapSvg.classList.add('is-dragging');
      if (mapSvg.setPointerCapture) mapSvg.setPointerCapture(e.pointerId);
    });
    mapSvg.addEventListener('pointermove', function (e) {
      if (!dragging) return;
      var r = mapSvg.getBoundingClientRect();
      var dx = e.clientX - last.x, dy = e.clientY - last.y;
      moved += Math.abs(dx) + Math.abs(dy);
      view.x -= dx / r.width * view.w;
      view.y -= dy / r.height * view.h;
      last = { x: e.clientX, y: e.clientY };
      applyView();
    });
    ['pointerup', 'pointercancel'].forEach(function (evt) {
      mapSvg.addEventListener(evt, function () {
        dragging = false;
        mapSvg.classList.remove('is-dragging');
      });
    });

    /* ctrl/⌘ + wheel zooms; a plain wheel is left to the page */
    mapSvg.addEventListener('wheel', function (e) {
      if (!e.ctrlKey && !e.metaKey) return;
      e.preventDefault();
      var pt = toView(e.clientX, e.clientY);
      zoomAt(e.deltaY < 0 ? 1.2 : 1 / 1.2, pt.x, pt.y);
    }, { passive: false });

    /* double-click zooms in on the point clicked */
    mapSvg.addEventListener('dblclick', function (e) {
      var pt = toView(e.clientX, e.clientY);
      zoomAt(1.9, pt.x, pt.y);
    });

    /* buttons */
    Array.prototype.forEach.call(document.querySelectorAll('.map__btn'), function (btn) {
      btn.addEventListener('click', function () {
        var c = centre();
        var how = btn.dataset.map;
        if (how === 'in') zoomAt(1.6, c.x, c.y);
        else if (how === 'out') zoomAt(1 / 1.6, c.x, c.y);
        else { view = { x: base.x, y: base.y, w: base.w, h: base.h }; applyView(); }
      });
    });

    /* keyboard, once a pin or the frame has focus */
    mapSvg.setAttribute('tabindex', '0');
    mapSvg.addEventListener('keydown', function (e) {
      var step = view.w * 0.12, c = centre(), used = true;
      if (e.key === 'ArrowLeft') view.x -= step;
      else if (e.key === 'ArrowRight') view.x += step;
      else if (e.key === 'ArrowUp') view.y -= step;
      else if (e.key === 'ArrowDown') view.y += step;
      else if (e.key === '+' || e.key === '=') zoomAt(1.6, c.x, c.y);
      else if (e.key === '-' || e.key === '_') zoomAt(1 / 1.6, c.x, c.y);
      else if (e.key === '0') { view = { x: base.x, y: base.y, w: base.w, h: base.h }; }
      else used = false;
      if (used) { e.preventDefault(); applyView(); }
    });

    applyView();
  }

  /* -------------------------------------------------------- avatar */
  // Show the photo only once it actually loads; otherwise the monogram stays.
  const avatar = document.getElementById('avatarImg');
  const mono = document.getElementById('avatarMono');
  if (avatar) {
    avatar.addEventListener('load', function () {
      if (avatar.naturalWidth > 1) {
        avatar.hidden = false;
        if (mono) mono.style.display = 'none';
      }
    });
    // Re-trigger for a cached hit that fired before the listener attached.
    if (avatar.complete && avatar.naturalWidth > 1) {
      avatar.hidden = false;
      if (mono) mono.style.display = 'none';
    }
  }

  /* ---------------------------------------------------------- misc */
  const year = document.getElementById('year');
  if (year) year.textContent = String(new Date().getFullYear());
})();
