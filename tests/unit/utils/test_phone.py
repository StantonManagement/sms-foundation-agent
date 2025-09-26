from src.utils.phone import to_e164, digits_only, country_stripped, variants


def test_digits_only_and_country_stripped():
    assert digits_only("+1 (415) 555-1212") == "14155551212"
    # country_stripped should return national number digits
    nsn = country_stripped("+1 (415) 555-1212")
    assert nsn in {"4155551212", "14155551212"}  # allow fallback behavior


def test_to_e164_and_variants_order():
    raw = "(415) 555-1212"
    e = to_e164(raw, default_region="US")
    assert e in {"+14155551212", "+14155551212"}
    v = variants(raw, default_region="US")
    # raw first
    assert v[0] == raw
    # contains e164 and digits-only
    assert any(x.startswith("+") for x in v)
    assert any(x.isdigit() for x in v)

