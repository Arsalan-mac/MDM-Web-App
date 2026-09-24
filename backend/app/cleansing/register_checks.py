"""RegisterNumber junk-detection rules (Stufe 1 of the original app's
three-stage RegisterNumber cleansing). Ported verbatim from
register_cleansing_module.py::register_number_issues - a pure function, no
DB/Streamlit dependency, so it's shared as-is between Quality Analysis's
Register-Nr. check (detection only) and the future RegisterNumber Cleansing
stage (detection + standardization + LLM cleanup), matching the original's
own "single source of truth" comment.
"""

import re

_PLACEHOLDERS = {
    "neu", "keine", "nicht vorhanden", "unbekannt", "not available", "k.a.", "k.a",
    "n/a", "na", "nav", "none", "fehlt", "offen", "tbd", "xxx", "-", "--", ".", "?",
    "0", "entfaellt", "entfällt", "nicht bekannt", "unknown", "no", "nein", "ohne",
    "in gruendung", "in gründung",
}
_PLACEHOLDER_WORDS = re.compile(
    r"\b(neu|unbekannt|nicht vorhanden|not available|siehe|folgt|beantragt)\b", re.IGNORECASE
)
_COURT_WORDS = re.compile(
    r"\b(amtsgericht|amtgericht|amstgericht|registergericht|district court|"
    r"handelsregister|vereinsregister|partnerschaftsregister|register-?\s?nr)\b",
    re.IGNORECASE,
)
_DUMMY_DIGITS = {"1234", "12345", "123456", "1234567", "12345678", "123456789", "1234567890"}

_REASON_ADDON = "Zusatztext/Gerichtsangabe"


def _norm_value(value) -> str:
    v = "" if value is None else str(value).strip()
    return "" if v.lower() in ("nan", "none", "<na>") else v


def register_number_issues(value) -> list[str]:
    """Checks a raw RegisterNumber value and returns the list of reasons it's
    junk (empty = clean). An empty value is clean (optional field -> 'Empty')."""
    v = _norm_value(value)
    if not v:
        return []
    reasons = []
    lv = v.lower()
    digits = re.sub(r"\D", "", v)

    if lv in _PLACEHOLDERS or _PLACEHOLDER_WORDS.search(lv):
        reasons.append("Platzhalter/Vermerk statt Nummer")
    if not digits:
        reasons.append("Keine Ziffer enthalten")
    if digits and len(set(digits)) == 1 and len(digits) >= 3:
        reasons.append(f"Ziffernwiederholung ({digits[0]}×{len(digits)})")
    if digits in _DUMMY_DIGITS:
        reasons.append("Verdaechtige Dummy-Folge")
    if len(v) < 3:
        reasons.append("Zu kurz (< 3 Zeichen)")
    if len(v) > 30 or _COURT_WORDS.search(v):
        reasons.append(_REASON_ADDON)
    return reasons
