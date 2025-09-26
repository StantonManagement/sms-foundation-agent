from __future__ import annotations

from typing import Tuple


def normalize_phone(number: str | None, default_region: str = "US") -> Tuple[str | None, str | None]:
    """Return (original, canonical) tuple for a phone number.

    Attempts to normalize to E.164 using phonenumbers if available; falls back to a
    naive normalization that keeps leading '+' and digits only. Returns (original, canonical).
    """
    if not number:
        return None, None
    original = number
    try:
        import phonenumbers  # type: ignore

        parsed = phonenumbers.parse(number, default_region)
        if not phonenumbers.is_valid_number(parsed):
            # Invalid -> fallback
            raise ValueError("invalid phone")
        canon = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        return original, canon
    except Exception:
        # Naive fallback: keep plus and digits, ensure leading '+' if it looked international
        digits = "".join(ch for ch in number if ch.isdigit())
        if number.strip().startswith("+"):
            canon = "+" + digits
        else:
            # Assume US country code for fallback if no '+'
            if len(digits) == 10:
                canon = "+1" + digits
            else:
                canon = "+" + digits if digits else None
        return original, canon

