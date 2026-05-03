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

      // Мобильное раскрытие dropdown категорий:
      // первый тап раскрывает список, второй тап может выполнить переход.
      var catalogItems = navbar.querySelectorAll('.menu-catalog');
      catalogItems.forEach(function (item) {
        var toggle = item.querySelector('.menu-catalog__toggle');
        if (!toggle) return;
        toggle.addEventListener('click', function (e) {
          if (!window.matchMedia('(max-width: 768px)').matches) {
            // На десктопе клик мышью оставляет фокус на ссылке и держит меню
            // открытым через :focus-within; убираем фокус только для «реального» клика.
            if (e.screenX === 0 && e.screenY === 0) return;
            if (document.activeElement === toggle) {
              window.setTimeout(function () {
                toggle.blur();
              }, 0);
            }
            return;
          }
          if (item.classList.contains('is-open')) return;
          e.preventDefault();
          item.classList.add('is-open');
          toggle.setAttribute('aria-expanded', 'true');
        });
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
