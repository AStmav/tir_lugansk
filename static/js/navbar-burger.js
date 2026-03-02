(function () {
  function initNavbarBurger() {
    document.querySelectorAll('.navbar__burger').forEach(function (btn) {
      if (btn.dataset.burgerInit) return;
      btn.dataset.burgerInit = '1';

      var navbar = btn.closest('.navbar');
      if (!navbar) return;

      btn.addEventListener('click', function () {
        var open = navbar.classList.toggle('menu-open');
        btn.setAttribute('aria-expanded', open ? 'true' : 'false');
      });

      // Закрыть меню при клике по ссылке (переход на другую страницу)
      var menu = navbar.querySelector('.navbar__menu');
      if (menu) {
        menu.querySelectorAll('a').forEach(function (link) {
          link.addEventListener('click', function () {
            navbar.classList.remove('menu-open');
            btn.setAttribute('aria-expanded', 'false');
          });
        });
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initNavbarBurger);
  } else {
    initNavbarBurger();
  }
})();
