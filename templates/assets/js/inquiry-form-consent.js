(function () {
  function validatePersonalDataConsent(form) {
    if (!form) {
      return true;
    }
    var checkbox = form.querySelector('input[name="personal_data_consent"]');
    var errorEl = form.querySelector(".modal__consent-error");
    if (!checkbox) {
      return true;
    }
    if (checkbox.checked) {
      if (errorEl) {
        errorEl.hidden = true;
      }
      return true;
    }
    if (errorEl) {
      errorEl.hidden = false;
    } else {
      alert("Необходимо согласие на обработку персональных данных.");
    }
    checkbox.focus();
    return false;
  }

  window.validatePersonalDataConsent = validatePersonalDataConsent;
})();
