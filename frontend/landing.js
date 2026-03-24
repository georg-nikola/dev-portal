/* =============================================
   Dev Portal — landing.js  v1.0.1
   Scroll animations, smooth scroll, mobile nav
   ============================================= */

(function () {
  'use strict';

  /* ---- Smooth scroll for anchor links ---- */
  document.querySelectorAll('a[href^="#"]').forEach(function (anchor) {
    anchor.addEventListener('click', function (e) {
      var target = document.querySelector(this.getAttribute('href'));
      if (!target) return;
      e.preventDefault();
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      // Close mobile nav if open
      closeMobileNav();
    });
  });

  /* ---- Nav scroll shadow ---- */
  var nav = document.getElementById('landingNav');
  if (nav) {
    window.addEventListener('scroll', function () {
      if (window.scrollY > 12) {
        nav.classList.add('landing-nav-scrolled');
      } else {
        nav.classList.remove('landing-nav-scrolled');
      }
    }, { passive: true });
  }

  /* ---- Mobile nav toggle ---- */
  var hamburger = document.getElementById('navHamburger');
  var navLinks  = document.getElementById('landingNavLinks');

  function closeMobileNav() {
    if (!navLinks || !hamburger) return;
    navLinks.classList.remove('landing-nav-links-open');
    hamburger.setAttribute('aria-expanded', 'false');
    hamburger.classList.remove('is-open');
  }

  if (hamburger && navLinks) {
    hamburger.addEventListener('click', function () {
      var isOpen = navLinks.classList.toggle('landing-nav-links-open');
      hamburger.setAttribute('aria-expanded', String(isOpen));
      hamburger.classList.toggle('is-open', isOpen);
    });

    // Close on outside click
    document.addEventListener('click', function (e) {
      if (!nav.contains(e.target)) {
        closeMobileNav();
      }
    });

    // Close on Escape
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') closeMobileNav();
    });
  }

  /* ---- Intersection Observer: fade-in-up on scroll ---- */
  var revealElements = document.querySelectorAll('.reveal');
  if (!revealElements.length) return;

  // Stagger cards inside grids
  document.querySelectorAll('.landing-features-grid, .landing-pricing-grid').forEach(function (grid) {
    grid.querySelectorAll('.reveal').forEach(function (el, i) {
      el.style.transitionDelay = (i * 80) + 'ms';
    });
  });

  // Stagger step items
  document.querySelectorAll('.landing-step.reveal').forEach(function (el, i) {
    el.style.transitionDelay = (i * 120) + 'ms';
  });

  var observer = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (entry.isIntersecting) {
        entry.target.classList.add('revealed');
        observer.unobserve(entry.target);
      }
    });
  }, {
    threshold: 0.12,
    rootMargin: '0px 0px -40px 0px'
  });

  revealElements.forEach(function (el) {
    observer.observe(el);
  });

})();
