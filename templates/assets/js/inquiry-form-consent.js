(function () {
  var CONSENT_MESSAGE =
    "Отметьте согласие на обработку персональных данных, чтобы отправить заявку.";

  function getConsentParts(form) {
    if (!form) {
      return null;
    }
    var checkbox = form.querySelector('input[name="personal_data_consent"]');
    var field = form.querySelector(".modal__field--consent");
    var errorEl = form.querySelector(".modal__consent-error");
    if (!checkbox) {
      return null;
    }
    return { checkbox: checkbox, field: field, errorEl: errorEl };
  }

  function isConsentErrorMessage(message) {
    if (!message) {
      return false;
    }
    var text = String(message).toLowerCase();
    return text.indexOf("согласие") !== -1 && text.indexOf("персональн") !== -1;
  }

  function showConsentError(form, message) {
    var parts = getConsentParts(form);
    if (!parts) {
      return false;
    }
    var text = message || CONSENT_MESSAGE;
    if (parts.errorEl) {
      parts.errorEl.textContent = text;
      parts.errorEl.hidden = false;
    }
    if (parts.field) {
      parts.field.classList.add("modal__field--consent-error");
    }
    parts.checkbox.setAttribute("aria-invalid", "true");
    if (parts.errorEl && parts.errorEl.id) {
      parts.checkbox.setAttribute("aria-describedby", parts.errorEl.id);
    }
    if (parts.field && typeof parts.field.scrollIntoView === "function") {
      parts.field.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
    parts.checkbox.focus({ preventScroll: true });
    return true;
  }

  function hideConsentError(form) {
    var parts = getConsentParts(form);
    if (!parts) {
      return;
    }
    if (parts.errorEl) {
      parts.errorEl.hidden = true;
    }
    if (parts.field) {
      parts.field.classList.remove("modal__field--consent-error");
    }
    parts.checkbox.removeAttribute("aria-invalid");
    parts.checkbox.removeAttribute("aria-describedby");
  }

  function validatePersonalDataConsent(form) {
    var parts = getConsentParts(form);
    if (!parts) {
      return true;
    }
    if (parts.checkbox.checked) {
      hideConsentError(form);
      return true;
    }
    showConsentError(form);
    return false;
  }

  /** @returns {boolean} true — ошибка согласия показана в форме, alert не нужен */
  function handleInquiryFormError(form, data) {
    if (data && data.success) {
      hideConsentError(form);
      return false;
    }
    if (data && isConsentErrorMessage(data.message)) {
      showConsentError(form, data.message);
      return true;
    }
    return false;
  }

  function initConsentForms() {
    document.querySelectorAll("form.modal__form").forEach(function (form) {
      var parts = getConsentParts(form);
      if (!parts) {
        return;
      }
      parts.checkbox.addEventListener("change", function () {
        if (parts.checkbox.checked) {
          hideConsentError(form);
        }
      });
      form.addEventListener("reset", function () {
        hideConsentError(form);
      });
    });
  }

  window.CONSENT_REQUIRED_MESSAGE = CONSENT_MESSAGE;
  window.validatePersonalDataConsent = validatePersonalDataConsent;
  window.handleInquiryFormError = handleInquiryFormError;
  window.hidePersonalDataConsentError = hideConsentError;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initConsentForms);
  } else {
    initConsentForms();
  }
})();
