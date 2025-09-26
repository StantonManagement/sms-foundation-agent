from __future__ import annotations

import re
from typing import Tuple


class LanguageDetector:
    """Very simple heuristic language detector for EN/ES/PT.

    - es: if text contains words like 'sí'/'si' (accent-insensitive) or common Spanish cues
    - pt: if text contains 'sim' or typical Portuguese cues
    - en: if text contains 'yes' or common English cues
    - unknown otherwise
    Returns (lang, confidence) where confidence is a float 0..1.
    """

    _es_patterns = [r"\bs[ií]\b", r"\bgracias\b", r"\bhola\b"]
    _pt_patterns = [r"\bsim\b", r"\bobrigado\b", r"\bolá\b"]
    _en_patterns = [r"\byes\b", r"\bhello\b", r"\bthanks\b"]

    @classmethod
    def detect(cls, text: str | None) -> Tuple[str, float]:
        if not text:
            return "unknown", 0.0
        lower = text.strip().lower()

        # Spanish
        if any(re.search(p, lower) for p in cls._es_patterns):
            return "es", 0.9

        # Portuguese
        if any(re.search(p, lower) for p in cls._pt_patterns):
            return "pt", 0.9

        # English
        if any(re.search(p, lower) for p in cls._en_patterns):
            return "en", 0.8

        return "unknown", 0.0
