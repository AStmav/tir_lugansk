(function() {
  var COLLAPSE_BREAKPOINT = 1200;
  var MOBILE_BREAKPOINT = 992;
  var MOBILE_CLASS = 'tl-admin-mobile';
  var PRODUCT_FOCUS_CLASS = 'tl-product-changelist-focus';
  var OVERLAY_ID = 'tl-admin-sidebar-overlay';

  function debounce(fn, delay) {
    var timer = null;
    return function() {
      clearTimeout(timer);
      timer = setTimeout(fn, delay);
    };
  }

  function getBody() {
    var body = document.body;
    if (!body || !body.classList.contains('sidebar-mini')) return null;
    return body;
  }

  function ensureOverlay() {
    var overlay = document.getElementById(OVERLAY_ID);
    if (overlay) return overlay;

    overlay = document.createElement('div');
    overlay.id = OVERLAY_ID;
    overlay.setAttribute('aria-hidden', 'true');
    document.body.appendChild(overlay);
    overlay.addEventListener('click', function() {
      var body = getBody();
      if (!body) return;
      body.classList.remove('sidebar-open');
      body.classList.add('sidebar-collapse');
      syncOverlay();
    });
    return overlay;
  }

  function syncOverlay() {
    var body = getBody();
    var overlay = ensureOverlay();
    if (!body) return;

    var isMobile = body.classList.contains(MOBILE_CLASS);
    var isOpen = body.classList.contains('sidebar-open');
    overlay.classList.toggle('is-active', isMobile && isOpen);
  }

  function syncSidebarMode() {
    var body = getBody();
    if (!body) return;

    var width = window.innerWidth;
    var isMobile = width < MOBILE_BREAKPOINT;
    var isProductChangelist = (
      body.classList.contains('app-shop') &&
      body.classList.contains('model-product') &&
      body.classList.contains('change-list')
    );

    body.classList.toggle(MOBILE_CLASS, isMobile);
    body.classList.toggle(PRODUCT_FOCUS_CLASS, isProductChangelist);

    if (isMobile) {
      // На мобильных по умолчанию закрыт, открывается кнопкой.
      body.classList.add('sidebar-collapse');
      body.classList.remove('sidebar-open');
    } else if (isProductChangelist) {
      // Для широких таблиц товаров: держим меню свернутым, чтобы максимум места отдать колонкам.
      body.classList.add('sidebar-collapse');
      body.classList.remove('sidebar-open');
    } else if (width <= COLLAPSE_BREAKPOINT) {
      // На планшете и небольших ноутбуках: компактный сайдбар.
      body.classList.add('sidebar-collapse');
      body.classList.remove('sidebar-open');
    } else {
      // На широких экранах: обычный режим.
      body.classList.remove('sidebar-collapse');
      body.classList.remove('sidebar-open');
    }

    syncOverlay();
  }

  function attachSidebarToggleWatcher() {
    var body = getBody();
    if (!body) return;

    var observer = new MutationObserver(function(mutations) {
      for (var i = 0; i < mutations.length; i++) {
        if (mutations[i].attributeName === 'class') {
          syncOverlay();
          break;
        }
      }
    });

    observer.observe(body, { attributes: true, attributeFilter: ['class'] });
  }

  document.addEventListener('keydown', function(e) {
    if (e.key !== 'Escape') return;
    var body = getBody();
    if (!body || !body.classList.contains(MOBILE_CLASS)) return;
    if (body.classList.contains('sidebar-open')) {
      body.classList.remove('sidebar-open');
      body.classList.add('sidebar-collapse');
      syncOverlay();
    }
  });

  document.addEventListener('DOMContentLoaded', function() {
    ensureOverlay();
    syncSidebarMode();
    attachSidebarToggleWatcher();
    window.addEventListener('resize', debounce(syncSidebarMode, 120));
  });
})();
