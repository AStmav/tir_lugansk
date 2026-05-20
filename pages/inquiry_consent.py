CONSENT_FIELD = "personal_data_consent"
CONSENT_REQUIRED_MESSAGE = "Необходимо согласие на обработку персональных данных."

_CONSENT_TRUTHY = frozenset({"on", "1", "true", "yes"})


def is_personal_data_consent_given(post_data) -> bool:
    value = post_data.get(CONSENT_FIELD)
    if value is True:
        return True
    if value is None:
        return False
    return str(value).strip().lower() in _CONSENT_TRUTHY
