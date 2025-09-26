from __future__ import annotations

import pytest

from src.services.language_detector import LanguageDetector


@pytest.mark.parametrize(
    "text,expected_lang",
    [
        ("Yes, please", "en"),
        ("yes", "en"),
        ("HELLO there", "en"),
    ],
)
def test_language_detector_english(text: str, expected_lang: str):
    lang, conf = LanguageDetector.detect(text)
    assert lang == expected_lang
    assert conf > 0


@pytest.mark.parametrize(
    "text",
    [
        "sí, gracias",
        "si por favor",
        "hola",
        "HOLA",
    ],
)
def test_language_detector_spanish(text: str):
    lang, conf = LanguageDetector.detect(text)
    assert lang == "es"
    assert conf > 0


@pytest.mark.parametrize(
    "text",
    [
        "sim",
        "obrigado",
        "olá",
        "OLÁ",
    ],
)
def test_language_detector_portuguese(text: str):
    lang, conf = LanguageDetector.detect(text)
    assert lang == "pt"
    assert conf > 0


@pytest.mark.parametrize(
    "text",
    [
        None,
        "",
        "12345",
        "unknownlanguagephrase",
    ],
)
def test_language_detector_unknown(text):
    lang, conf = LanguageDetector.detect(text)
    assert lang == "unknown"
    assert conf == 0.0

