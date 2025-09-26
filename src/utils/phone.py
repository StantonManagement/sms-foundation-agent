from __future__ import annotations

from typing import Iterable, Tuple


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


def to_e164(number: str | None, default_region: str = "US") -> str | None:
    """Return E.164 string for a phone if valid, else None.

    Uses `phonenumbers` when available; falls back to naive logic similar to
    normalize_phone. Does not raise.
    """
    if not number:
        return None
    try:
        import phonenumbers  # type: ignore

        parsed = phonenumbers.parse(number, default_region)
        if not phonenumbers.is_valid_number(parsed):
            return None
        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except Exception:
        # Fallback: retain plus + digits, or assume US if 10 digits
        digits = "".join(ch for ch in number if ch.isdigit())
        if not digits:
            return None
        if number.strip().startswith("+"):
            return "+" + digits
        if len(digits) == 10:
            return "+1" + digits
        return "+" + digits


def digits_only(number: str | None) -> str | None:
    """Return only digits from the input, or None if empty/None."""
    if not number:
        return None
    d = "".join(ch for ch in number if ch.isdigit())
    return d or None


def country_stripped(number: str | None, default_region: str = "US") -> str | None:
    """Return national significant number (no country code) as digits, if parseable.

    If not parseable, attempt to best-effort strip leading '+<cc>' for common cases,
    else return digits-only as fallback.
    """
    if not number:
        return None
    try:
        import phonenumbers  # type: ignore

        parsed = phonenumbers.parse(number, default_region)
        if not phonenumbers.is_possible_number(parsed):
            # fall back
            raise ValueError("not possible")
        nsn = phonenumbers.national_significant_number(parsed)
        return nsn or None
    except Exception:
        d = digits_only(number)
        if not d:
            return None
        # If looks like +1XXXXXXXXXX, strip 1 for US as common default
        if number.strip().startswith("+") and len(d) > 10 and d.startswith("1"):
            return d[1:]
        return d


def _dedupe_ordered(values: Iterable[str | None]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        if not v:
            continue
        if v in seen:
            continue
        seen.add(v)
        out.append(v)
    return out


def variants(raw: str | None, default_region: str = "US") -> list[str]:
    """Produce ordered candidate phone variants for lookup.

    Order: raw, E.164, country-stripped (NSN), digits-only; deduplicated.
    """
    if not raw:
        return []
    e164 = to_e164(raw, default_region)
    nsn = country_stripped(raw, default_region)
    digs = digits_only(raw)
    return _dedupe_ordered([raw, e164, nsn, digs])
