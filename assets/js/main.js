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
  // The address is stored as reversed base64 in a single data-e attribute and
  // decoded here. No fragment of it — not the local part, not the domain, not
  // an "[at]" spelling — appears anywhere in the served HTML, so a harvester
  // scraping the raw page finds nothing to reassemble.
  Array.prototype.forEach.call(document.querySelectorAll('.js-mail'), function (el) {
    var token = el.getAttribute('data-e');
    if (!token) return;
    var addr;
    try {
      addr = atob(token.split('').reverse().join(''));
    } catch (e) {
      return;                       // malformed token: leave the link untouched
    }

    var label = el.querySelector('.js-mail-text');
    if (!label) {
      // Icon link. Its text never shows the address, but writing the mailto:
      // href on load would still park it in the live DOM for anything that
      // executes JS and reads the tree. So arm it on the first sign of human
      // intent — hover, keyboard focus or touch — which always precedes the
      // click, keeping it a single click for real visitors.
      var arm = function () {
        if (el.dataset.armed) return;
        el.href = 'ma' + 'ilto:' + addr;
        el.dataset.armed = '1';
      };
      ['mouseenter', 'focus', 'touchstart'].forEach(function (evt) {
        el.addEventListener(evt, arm, { passive: true, once: true });
      });
      // Belt and braces: if a click somehow lands unarmed, arm and follow it.
      el.addEventListener('click', function (e) {
        if (el.dataset.armed) return;
        e.preventDefault();
        arm();
        window.location.href = el.href;
      });
      return;
    }

    // Contact button: hold the address back until a human actually asks for
    // it. Rendering it on load would put it on screen — and in the live DOM,
    // where a headless scraper that executes JS would read it straight off.
    el.addEventListener('click', function (e) {
      if (el.dataset.revealed) return;   // already shown: let the mailto fire
      e.preventDefault();
      label.textContent = addr;
      el.href = 'ma' + 'ilto:' + addr;
      el.dataset.revealed = '1';
    });
  });

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
