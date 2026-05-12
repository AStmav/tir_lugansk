(() => {
  const TRIGGER_SELECTOR = "[data-image-lightbox]";
  let lightboxEl = null;
  let imageEl = null;
  let closeBtnEl = null;
  let lastActiveElement = null;
  let previousBodyOverflow = "";

  function ensureLightbox() {
    if (lightboxEl) {
      return;
    }

    lightboxEl = document.createElement("div");
    lightboxEl.className = "image-lightbox";
    lightboxEl.setAttribute("aria-hidden", "true");
    lightboxEl.innerHTML = `
      <div class="image-lightbox__backdrop" data-image-lightbox-close="backdrop">
        <div class="image-lightbox__dialog" role="dialog" aria-modal="true" aria-label="Просмотр изображения">
          <button type="button" class="image-lightbox__close" aria-label="Закрыть изображение" data-image-lightbox-close="button">&times;</button>
          <img class="image-lightbox__image" src="" alt="">
        </div>
      </div>
    `;

    document.body.appendChild(lightboxEl);
    imageEl = lightboxEl.querySelector(".image-lightbox__image");
    closeBtnEl = lightboxEl.querySelector(".image-lightbox__close");

    lightboxEl.addEventListener("click", (event) => {
      const closeTarget = event.target.closest("[data-image-lightbox-close]");
      if (closeTarget) {
        closeLightbox();
      }
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && isOpen()) {
        closeLightbox();
      }
    });
  }

  function isOpen() {
    return lightboxEl && lightboxEl.classList.contains("image-lightbox--active");
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

  function openLightbox(src, alt) {
    ensureLightbox();
    if (!src) {
      return;
    }

    imageEl.src = src;
    imageEl.alt = alt || "Изображение товара";
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

    const src = extractSource(triggerEl);
    const alt = extractAlt(triggerEl);
    openLightbox(src, alt);
  });
})();
