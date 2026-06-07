(() => {
  const TRIGGER_SELECTOR = "[data-image-lightbox]";
  const GALLERY_SELECTOR = "[data-image-lightbox-gallery]";

  let lightboxEl = null;
  let imageEl = null;
  let closeBtnEl = null;
  let prevBtnEl = null;
  let nextBtnEl = null;
  let lastActiveElement = null;
  let previousBodyOverflow = "";
  let galleryItems = [];
  let currentIndex = 0;
  let activeGallery = null;

  function ensureLightbox() {
    if (lightboxEl) {
      return;
    }

    lightboxEl = document.createElement("div");
    lightboxEl.className = "image-lightbox";
    lightboxEl.setAttribute("aria-hidden", "true");
    lightboxEl.innerHTML = `
      <div class="image-lightbox__backdrop" data-image-lightbox-close="backdrop">
        <button type="button" class="image-lightbox__nav image-lightbox__nav--prev" aria-label="Предыдущее изображение" hidden>
          <span aria-hidden="true">&lsaquo;</span>
        </button>
        <div class="image-lightbox__dialog" role="dialog" aria-modal="true" aria-label="Просмотр изображения">
          <button type="button" class="image-lightbox__close" aria-label="Закрыть изображение" data-image-lightbox-close="button">&times;</button>
          <img class="image-lightbox__image" src="" alt="">
        </div>
        <button type="button" class="image-lightbox__nav image-lightbox__nav--next" aria-label="Следующее изображение" hidden>
          <span aria-hidden="true">&rsaquo;</span>
        </button>
      </div>
    `;

    document.body.appendChild(lightboxEl);
    imageEl = lightboxEl.querySelector(".image-lightbox__image");
    closeBtnEl = lightboxEl.querySelector(".image-lightbox__close");
    prevBtnEl = lightboxEl.querySelector(".image-lightbox__nav--prev");
    nextBtnEl = lightboxEl.querySelector(".image-lightbox__nav--next");

    lightboxEl.addEventListener("click", (event) => {
      if (event.target.closest('[data-image-lightbox-close="button"]')) {
        closeLightbox();
        return;
      }
      if (event.target.getAttribute("data-image-lightbox-close") === "backdrop") {
        closeLightbox();
      }
    });

    prevBtnEl.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      showSlide(currentIndex - 1);
    });

    nextBtnEl.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      showSlide(currentIndex + 1);
    });

    document.addEventListener("keydown", (event) => {
      if (!isOpen()) {
        return;
      }
      if (event.key === "Escape") {
        closeLightbox();
        return;
      }
      if (galleryItems.length <= 1) {
        return;
      }
      if (event.key === "ArrowLeft") {
        event.preventDefault();
        showSlide(currentIndex - 1);
      } else if (event.key === "ArrowRight") {
        event.preventDefault();
        showSlide(currentIndex + 1);
      }
    });
  }

  function isOpen() {
    return lightboxEl && lightboxEl.classList.contains("image-lightbox--active");
  }

  function normalizeSrc(src) {
    if (!src) {
      return "";
    }
    try {
      return new URL(src, window.location.href).href;
    } catch (_error) {
      return src;
    }
  }

  function extractSource(triggerEl) {
    const explicitSrc = triggerEl.getAttribute("data-lightbox-src");
    if (explicitSrc) {
      return explicitSrc;
    }

    const img = triggerEl.tagName === "IMG" ? triggerEl : triggerEl.querySelector("img");
    return img ? img.getAttribute("src") : "";
  }

  function extractAlt(triggerEl) {
    const explicitAlt = triggerEl.getAttribute("data-lightbox-alt");
    if (explicitAlt) {
      return explicitAlt;
    }

    const img = triggerEl.tagName === "IMG" ? triggerEl : triggerEl.querySelector("img");
    return img ? (img.getAttribute("alt") || "Изображение товара") : "Изображение товара";
  }

  function collectGalleryItems(triggerEl) {
    const gallery = triggerEl.closest(GALLERY_SELECTOR);
    if (!gallery) {
      return [
        {
          src: extractSource(triggerEl),
          alt: extractAlt(triggerEl),
        },
      ];
    }

    const items = [];
    const seen = new Set();

    gallery.querySelectorAll(".product__thumbnail img").forEach((img) => {
      const src = img.getAttribute("src");
      if (!src || seen.has(src)) {
        return;
      }
      seen.add(src);
      items.push({
        src,
        alt: img.getAttribute("alt") || "Изображение товара",
      });
    });

    if (items.length === 0) {
      const mainImg = gallery.querySelector(".product__image-main img");
      if (mainImg) {
        const src = mainImg.getAttribute("src");
        if (src) {
          items.push({
            src,
            alt: mainImg.getAttribute("alt") || "Изображение товара",
          });
        }
      }
    }

    return items;
  }

  function findSlideIndex(items, triggerEl) {
    const clickedSrc = normalizeSrc(extractSource(triggerEl));
    if (!clickedSrc) {
      return 0;
    }

    const index = items.findIndex((item) => normalizeSrc(item.src) === clickedSrc);
    if (index >= 0) {
      return index;
    }

    const gallery = triggerEl.closest(GALLERY_SELECTOR);
    const mainImg = gallery ? gallery.querySelector(".product__image-main img") : null;
    if (mainImg) {
      const mainSrc = normalizeSrc(mainImg.getAttribute("src"));
      const mainIndex = items.findIndex((item) => normalizeSrc(item.src) === mainSrc);
      if (mainIndex >= 0) {
        return mainIndex;
      }
    }

    return 0;
  }

  function updateNavButtons() {
    const hasMany = galleryItems.length > 1;
    prevBtnEl.hidden = !hasMany;
    nextBtnEl.hidden = !hasMany;
  }

  function syncProductGallery(index) {
    if (!activeGallery) {
      return;
    }

    const item = galleryItems[index];
    if (!item) {
      return;
    }

    const mainImg = activeGallery.querySelector(".product__image-main img");
    if (mainImg) {
      mainImg.src = item.src;
      mainImg.alt = item.alt;
    }

    const targetSrc = normalizeSrc(item.src);
    activeGallery.querySelectorAll(".product__thumbnail").forEach((thumbnail) => {
      const thumbImg = thumbnail.querySelector("img");
      const isActive = thumbImg && normalizeSrc(thumbImg.getAttribute("src")) === targetSrc;
      thumbnail.classList.toggle("product__thumbnail--active", isActive);
    });
  }

  function showSlide(index) {
    if (!galleryItems.length) {
      return;
    }

    currentIndex = (index + galleryItems.length) % galleryItems.length;
    const item = galleryItems[currentIndex];
    imageEl.src = item.src;
    imageEl.alt = item.alt || "Изображение товара";
    syncProductGallery(currentIndex);
  }

  function openLightbox(triggerEl) {
    ensureLightbox();

    activeGallery = triggerEl.closest(GALLERY_SELECTOR);
    galleryItems = collectGalleryItems(triggerEl).filter((item) => item.src);
    if (!galleryItems.length) {
      return;
    }

    currentIndex = findSlideIndex(galleryItems, triggerEl);
    showSlide(currentIndex);
    updateNavButtons();

    lightboxEl.classList.add("image-lightbox--active");
    lightboxEl.setAttribute("aria-hidden", "false");

    previousBodyOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    lastActiveElement = document.activeElement;
    closeBtnEl.focus();
  }

  function closeLightbox() {
    if (!isOpen()) {
      return;
    }

    lightboxEl.classList.remove("image-lightbox--active");
    lightboxEl.setAttribute("aria-hidden", "true");
    imageEl.removeAttribute("src");
    galleryItems = [];
    currentIndex = 0;
    activeGallery = null;
    updateNavButtons();
    document.body.style.overflow = previousBodyOverflow;

    if (lastActiveElement && typeof lastActiveElement.focus === "function") {
      lastActiveElement.focus();
    }
  }

  document.addEventListener("click", (event) => {
    const triggerEl = event.target.closest(TRIGGER_SELECTOR);
    if (!triggerEl) {
      return;
    }

    event.preventDefault();
    event.stopPropagation();
    openLightbox(triggerEl);
  });
})();
