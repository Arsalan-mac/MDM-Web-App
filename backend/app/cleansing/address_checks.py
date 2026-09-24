"""Adress-Analyse: the Address field check.

Ported from the original app's address_cleansing_module.py::check_addresses
(plus its small helpers from address_common.py, plz_cleansing_module.py, and
sap_address_module.py). Detects: placeholder text, legal-form-in-address,
contact-info-in-address, too-long/too-short addresses, missing house
numbers, and city/postal-code text embedded in the address field.

Deliberately NOT ported yet (see docs/ROADMAP.md):
- PLZ format check (plz_cleansing_module.check_zipcodes) and the City check
  (city_region_module.check_city_region) - both depend on the Referenzdaten
  stage (a curated PLZ_RULES table plus an optional GeoNames import), which
  is its own vertical slice, not yet built.
- The Claude-based correction step for KONTAKTINFO/RECHTSFORM/ADRESSE_ZU_LANG
  findings (the original's _ki_correct_addresses) - pairs naturally with the
  Phase 1d chat-with-data agent work.

`rules` is accepted for interface stability with the eventual Referenzdaten
port, but every rule lookup here degrades gracefully to None (checked
explicitly at each call site, exactly as the original code already does),
so passing `{}` today is correct, not a stub - it just means postal-code
text embedded in an address can still be *detected* by exact match against
the Mandant's own ZipCode, but not upgraded to a country-rule-validated
conflict.
"""

import re
from typing import Any

import pandas as pd

SAP_ADDR_MAX = 60 + 3 * 40  # STREET (60) + STR_SUPPL1-3 (3x40), mirrors sap_address_module

ACTION_REPLACE = "ERSETZEN"
ACTION_CLEAR = "LEEREN"
ACTION_MANUAL = "MANUELL"

CONF_HIGH, CONF_MED, CONF_LOW = "hoch", "mittel", "niedrig"

CAT_PLATZHALTER = "PLATZHALTER"
CAT_PLZ_IM_ADRESSFELD = "PLZ_IM_ADRESSFELD"
CAT_ORT_IM_ADRESSFELD = "ORT_IM_ADRESSFELD"
CAT_KONTAKTINFO = "KONTAKTINFO"
CAT_RECHTSFORM = "RECHTSFORM"
CAT_ADRESSE_FEHLT = "ADRESSE_FEHLT"
CAT_ADRESSE_ZU_KURZ = "ADRESSE_ZU_KURZ"
CAT_KEINE_HAUSNUMMER = "KEINE_HAUSNUMMER"
CAT_FIRMENNAME = "FIRMENNAME_STATT_ADRESSE"
CAT_ADRESSE_ZU_LANG = "ADRESSE_ZU_LANG"

CATEGORY_LABEL = {
    CAT_PLATZHALTER: "Platzhalter → leeren",
    CAT_PLZ_IM_ADRESSFELD: "PLZ im Adressfeld abtrennen",
    CAT_ORT_IM_ADRESSFELD: "Ort im Adressfeld abtrennen",
    CAT_KONTAKTINFO: "Kontaktinfo in Adresse (manuell)",
    CAT_RECHTSFORM: "Rechtsform in Adresse (manuell)",
    CAT_ADRESSE_FEHLT: "Adresse fehlt (manuell)",
    CAT_ADRESSE_ZU_KURZ: "Adresse zu kurz (manuell)",
    CAT_KEINE_HAUSNUMMER: "Keine Hausnummer (manuell)",
    CAT_FIRMENNAME: "Firmenname/Notiz statt Adresse (manuell)",
    CAT_ADRESSE_ZU_LANG: "Adresse zu lang für SAP-Felder (manuell)",
}

# Priority order for picking the one category shown per row (a row can match
# several checks - the highest-priority one drives Aktion/Confidence).
_CAT_PRIORITY = [
    CAT_PLATZHALTER, CAT_ADRESSE_FEHLT, CAT_ADRESSE_ZU_LANG, CAT_KONTAKTINFO, CAT_RECHTSFORM,
    CAT_FIRMENNAME, CAT_ADRESSE_ZU_KURZ, CAT_KEINE_HAUSNUMMER, CAT_PLZ_IM_ADRESSFELD,
    CAT_ORT_IM_ADRESSFELD,
]
# Categories the app can auto-apply (ERSETZEN/LEEREN); everything else is MANUELL.
_AUTO_CATS = {CAT_PLATZHALTER, CAT_PLZ_IM_ADRESSFELD, CAT_ORT_IM_ADRESSFELD}

_BASE_COLS = [
    "IDParty", "UserCode_Added", "UserCode_Kummerer", "CompanyName", "IsOrganisation",
    "IsIndividual", "IsInactive", "Address", "City", "ZipCode", "CountryCode",
]

# ── Regexes (verbatim from the original, wording kept so Reason text is stable) ──
_LEGAL_FORMS_RE = re.compile(r"\b(GMBH|AG|KG|LTD|INC|S\.R\.L|S\.A\.|S\.P\.A\.|CO\.|LIMITED|HOLDING|SE|UG)\b")
_CONTACT_INFO_RE = re.compile(r"(@|WWW\.|HTTP|\.COM|\.DE|\+49|0049|Z\.HD\.|ATTN:|TEL:|FAX:)")
_PLACEHOLDER_EXACT = {
    "UNBEKANNT", "UNKNOWN", "TBA", "TBD", "ADRESSE FEHLT", "N/A", "NA", "N.A.", "NONE", "NULL", "KEINE",
    "KEINE ANGABE", "K.A.", "K. A.", "NICHT BEKANNT", "NOT AVAILABLE", "NOT KNOWN", "NO ADDRESS",
    "KEINE ADRESSE", "SIEHE OBEN", "WIE OBEN", "DTO", "DITO", "TEST", "X", "XX", "XXX", "XXXX",
    "0", "00", "000", "0000", "?", "??", "???",
}
_PLACEHOLDER_PUNCT_RE = re.compile(r"^[\s\-–—_.,;:/\\*#+?!'\"()\[\]]+$")
_STREET_WORD_RE = re.compile(
    r"(straße|strasse|str\.|\bstr\b|weg\b|gasse\b|platz\b|allee\b|ring\b|damm\b|ufer\b|chaussee\b|steig\b|"
    r"markt\b|pfad\b|hof\b|zeile\b|promenade\b|siedlung\b|kai\b|brücke\b|bruecke\b|road\b|\brd\b|street\b|"
    r"\bst\b|avenue\b|\bave\b|lane\b|\bln\b|drive\b|\bdr\b|\bvia\b|viale\b|piazza\b|corso\b|\brue\b|"
    r"boulevard\b|\bbd\b|\bblvd\b|chemin\b|calle\b|avenida\b|plaza\b|\bul\b|\bul\.|ulica\b|ulice\b|nám|"
    r"třída|laan\b|straat\b|plein\b|gracht\b|kade\b|postfach|po box|p\.o\.|boîte|casella|apartado|c/o|"
    r"carrer\b|camino\b|paseo\b|\brua\b|praça|largo\b|park\b|court\b|close\b|\bway\b|place\b|square\b|"
    r"terrace\b|crescent\b|gardens\b|grove\b|hill\b|\brow\b|walk\b|highway|\bhwy\b|route\b|\brt\b|pkwy\b|"
    r"circle\b|\bcir\b|trail\b|estate|industrial|zone\b|zona\b|area\b|parc\b|quai\b|impasse\b|"
    r"allée|sokak|cadde|\bcad\b|\bsok\b|mahalle|\bmah\b|utca\b|\btér\b|\bút\b|strada\b|bulevard|"
    r"nábřeží|\bnábř|sídliště|náměstí|\bnám\.|ringstr|hauptstr|bahnhofstr|dorfstr|kirchstr|schulstr|"
    r"industriestr|gewerbe|zentrum|center|centre|tower|building|gebäude|haus\b|villa\b|\blot\b|\bunit\b|"
    r"suite\b|floor\b|\bfl\b|etage|stock\b|\bog\b|\beg\b|\bdg\b|top\b|stiege|tür\b|tuer\b)", re.I,
)
_RE_HAUS_PREFIX = re.compile(r"(?i)^haus\s+")

# From sap_address_module._RE_PURE_NR: a segment that's only a house-number
# reference ("Nr. 98", "23") with no street name at all.
_RE_PURE_NR = re.compile(r"(?i)^(?:(?:nr|no|n)[°.:]{0,2}\s*)?\d+\s?[a-zA-Z]?(?:\s*[-–/]\s*[0-9a-zA-Z]{1,4})*\s*$")

# From plz_cleansing_module: alnum-only normalization and known country prefixes
# used before a postal code ("D-47802", "A-1010").
_ALNUM_RE = re.compile(r"[^A-Z0-9]")
_PREFIX_TOKENS = {
    "A", "AT", "D", "DE", "CH", "F", "FR", "I", "IT", "B", "BE", "NL", "L", "LU",
    "E", "ES", "P", "PT", "S", "SE", "N", "NO", "PL", "CZ", "SK", "HU", "H", "RO",
    "DK", "FI", "GB", "UK", "IE", "US", "CA",
}

_SEP = r"\s*(?:[,;/:]|\s[-–]\s)\s*"
_PUNCT_SEP = re.compile(r"[,;/:]|\s[-–]\s")
_HN_END = re.compile(r"(?:\d+\s*[a-zA-Z]?|\d+\s*[/\-]\s*\d+[a-zA-Z]?)\s*$")
_PLZ_PREFIX = "(?:(?:" + "|".join(sorted(_PREFIX_TOKENS, key=len, reverse=True)) + r")[-\s]?)?"
_PO_BOX_BEFORE = re.compile(
    r"(postfach|p\.?\s*o\.?\s*box|po\s*box|\bbox|postbus|\bpf\b|c\.?\s*p\.?|casella\s+postale|\bbp\b|apartado|"
    r"skr(?:ytka)?\.?\s*poczt\w*|\bnr\.?|\bno\.?|n°|tel\.?|fax|\btop|stiege|stg\.?|tür|tuer|\bzi\.?|\bap\.?|"
    r"\bapt\.?|\bunit|\bsuite|\bste\.?|\broom|\bfloor|\bfl\.?|\bog\b|\beg\b|\bstock)\s*$", re.I,
)


def norm_text(v: Any) -> str:
    """NULL/NaN -> '' (str(None) would otherwise produce the text 'None')."""
    if v is None:
        return ""
    if not isinstance(v, str):
        try:
            if pd.isna(v):
                return ""
        except (TypeError, ValueError):
            pass
    return str(v).strip()


def _alnum(s: str) -> str:
    return _ALNUM_RE.sub("", s.upper())


def _is_placeholder(addr: str) -> bool:
    up = addr.upper().strip()
    if not up:
        return False
    if up in _PLACEHOLDER_EXACT or _PLACEHOLDER_PUNCT_RE.match(up):
        return True
    core = re.sub(r"[^A-Z0-9]", "", up)
    return bool(core) and len(set(core)) == 1 and len(core) >= 3 and core[0] in "X0-9"


def _looks_like_address(addr: str) -> bool:
    """Loose plausibility check: does this still look like an address?

    Shared by check_addresses (raw address detection) and, eventually, the
    Claude-based correction step's acceptance gate, so both apply the same
    bar. Two cases count as NOT an address: (a) no digit at all, or (b) the
    whole thing is only a house-number reference with no street name
    ("Nr. 67", "Haus Nr. 20").
    """
    addr = (addr or "").strip()
    if len(addr) < 4:
        return False
    if not any(c.isdigit() for c in addr):
        return False
    core = _RE_HAUS_PREFIX.sub("", addr).strip()
    if _RE_PURE_NR.match(core):
        return False
    return True


def _looks_like_street(text: str) -> bool:
    return len(text) >= 4 and (any(ch.isdigit() for ch in text) or bool(_STREET_WORD_RE.search(text)))


def _strip_city_plz(addr: str, city: str, plz: str, rule) -> tuple[str, bool, bool, bool]:
    """Strip '<PLZ> <City>' / '<City>' / '<PLZ>' from the start/end of the address
    field, when City = Mandant.City and the PLZ is plausible.

    Returns (rest, found_plz, found_city, plz_conflict) - plz_conflict means a
    plausible PLZ was found in the address text but it differs from
    Mandant.ZipCode.
    """
    s = addr
    found_plz = found_city = plz_conflict = False
    city_k = norm_text(city).casefold()
    plz_core = _alnum(norm_text(plz)) if plz else ""
    plz_pat = _PLZ_PREFIX + r"[A-Z0-9][A-Z0-9\-]{2,9}(?:\s[A-Z0-9]{2,4})?"

    def _plz_ok(cand: str, before: str) -> bool:
        nonlocal plz_conflict
        if not cand or _PO_BOX_BEFORE.search(before):
            return False
        core = _alnum(cand)
        if not core:
            return False
        if core == plz_core:
            return True
        m_pre = re.match(_PLZ_PREFIX + r"(.*)$", cand)
        core2 = _alnum(m_pre.group(1)) if m_pre and m_pre.group(1) else core
        ok = rule is not None and len(core2) >= 4 and rule.normalize(core2) is not None
        if ok:
            plz_conflict = True
        return ok

    for _ in range(2):
        changed = False
        if city_k:
            m = re.search(
                r"([\s,;/\-–:]+)(" + plz_pat + r")?[\s,;/\-–:]*" + re.escape(city) + r"\s*\.?\s*$",
                s, flags=re.I,
            )
            if m and m.start() > 0:
                cand = norm_text(m.group(2) or "")
                cand_ok = _plz_ok(cand, s[:m.start()])
                if cand and not cand_ok:
                    m = re.search(r"([\s,;/\-–:]+)" + re.escape(city) + r"\s*\.?\s*$", s, flags=re.I)
                    cand = ""
                if m and m.start() > 0:
                    rest = s[:m.start()]
                    has_punct = bool(_PUNCT_SEP.search(m.group(1)))
                    if has_punct or _HN_END.search(rest):
                        s = rest
                        found_city = changed = True
                        found_plz = found_plz or bool(cand and cand_ok)
            m = re.match(r"^\s*(" + plz_pat + r")?[\s,;/\-–:]*" + re.escape(city) + _SEP + r"(?=\S)", s, flags=re.I)
            if m and m.end() < len(s):
                cand = norm_text(m.group(1) or "")
                cand_ok = _plz_ok(cand, "")
                if not cand or cand_ok:
                    s = s[m.end():]
                    found_city = changed = True
                    found_plz = found_plz or cand_ok
        if plz_core and len(plz_core) >= 4:
            m = re.search(r"[\s,;/\-–:]+" + _PLZ_PREFIX + re.escape(norm_text(plz)) + r"\s*\.?\s*$", s, flags=re.I)
            if m and m.start() > 0 and not _PO_BOX_BEFORE.search(s[:m.start()]):
                s = s[:m.start()]
                found_plz = changed = True
            m = re.match(r"^\s*" + _PLZ_PREFIX + re.escape(norm_text(plz)) + _SEP + r"(?=\S)", s, flags=re.I)
            if m and m.end() < len(s):
                s = s[m.end():]
                found_plz = changed = True
        if not changed:
            break

    rest = re.sub(r"\s+", " ", s).strip(" ,;/-–:")
    if found_plz:
        rest = re.sub(
            r"[\s,;/\-–:]*\b(?:P\.?\s*C\.?|PLZ|CP|C\.P\.|Postal\s+Code|Zip(?:\s*Code)?|Postcode)\s*[:.]?\s*$",
            "", rest, flags=re.I,
        ).strip(" ,;/-–:")
    if plz_core and (found_city or found_plz) and _alnum(rest) == plz_core:
        rest, found_plz = "", True
    return rest, found_plz, found_city, plz_conflict


def check_addresses(rows: list[dict], rules: dict, ts: str) -> list[dict]:
    """Check the Address field of every row. `rows` is a list of dicts with
    at least the keys in _BASE_COLS (Mandant.__table__ columns, JSON-safe).
    `rules` maps CountryCode -> a PLZ rule object with a `.normalize()`
    method, or is empty (see module docstring) - not yet populated by
    anything in this codebase.

    Returns one dict per flagged Mandant, ready to become a JunkAddress row
    (see app/cleansing/address_service.py).
    """
    out = []
    for r in rows:
        addr_raw = r.get("Address")
        addr = norm_text(addr_raw)
        addr_up = addr.upper()
        city = norm_text(r.get("City"))
        city_up = city.upper()
        cc = norm_text(r.get("CountryCode")).upper()
        plz = norm_text(r.get("ZipCode"))
        reasons: list[str] = []
        cats: set[str] = set()
        address_neu = ""
        plz_conflict = False

        if not addr:
            reasons.append("Adresse fehlt")
            cats.add(CAT_ADRESSE_FEHLT)
        else:
            if _is_placeholder(addr):
                reasons.append("Platzhalter-Text")
                cats.add(CAT_PLATZHALTER)
            if _LEGAL_FORMS_RE.search(addr_up):
                reasons.append("Rechtsform in Adresse")
                cats.add(CAT_RECHTSFORM)
            if _CONTACT_INFO_RE.search(addr_up):
                reasons.append("Kontaktinfo in Adresse")
                cats.add(CAT_KONTAKTINFO)
            if len(addr) > SAP_ADDR_MAX:
                reasons.append("Adresse zu lang")
                cats.add(CAT_ADRESSE_ZU_LANG)
            if len(addr) < 4:
                reasons.append("Adresse zu kurz")
                cats.add(CAT_ADRESSE_ZU_KURZ)
            if len(addr) > 3 and not _looks_like_address(addr):
                only_housenum = any(c.isdigit() for c in addr)
                reasons.append("Nur Hausnummer, keine Straße" if only_housenum else "Keine Hausnummer")
                cats.add(CAT_KEINE_HAUSNUMMER)
                if CAT_PLATZHALTER not in cats and not _STREET_WORD_RE.search(addr):
                    reasons.append("Firmenname statt Adresse")
                    cats.add(CAT_FIRMENNAME)
            if city_up and city_up in addr_up:
                rest, f_plz, f_city, plz_conflict = _strip_city_plz(addr, city, plz, rules.get(cc))
                if len(addr_up) < len(city_up) + 5:
                    reasons.append("Stadtname im Adressfeld")
                    cats.add(CAT_ORT_IM_ADRESSFELD)
                elif f_city:
                    if f_plz:
                        reasons.append(
                            "PLZ im Adressfeld (weicht von ZipCode ab)" if plz_conflict else "PLZ im Adressfeld"
                        )
                        cats.add(CAT_PLZ_IM_ADRESSFELD)
                    reasons.append("Ort im Adressfeld")
                    cats.add(CAT_ORT_IM_ADRESSFELD)
                    if _looks_like_street(rest):
                        address_neu = rest
            elif plz and len(_alnum(plz)) >= 4 and plz.upper() in addr_up:
                rest, f_plz, _f_city, plz_conflict = _strip_city_plz(addr, "", plz, rules.get(cc))
                if f_plz:
                    reasons.append("PLZ im Adressfeld")
                    cats.add(CAT_PLZ_IM_ADRESSFELD)
                    if _looks_like_street(rest):
                        address_neu = rest

        if not reasons:
            continue

        kat = next(c for c in _CAT_PRIORITY if c in cats)
        manual = bool(cats - _AUTO_CATS)
        if kat == CAT_PLATZHALTER:
            aktion, conf, neu = ACTION_CLEAR, CONF_HIGH, ""
        elif manual or not address_neu:
            aktion, conf, neu = ACTION_MANUAL, "", address_neu
        else:
            aktion, conf, neu = ACTION_REPLACE, CONF_HIGH, address_neu
            if (CAT_PLZ_IM_ADRESSFELD in cats and CAT_ORT_IM_ADRESSFELD not in cats) or plz_conflict:
                conf = CONF_MED

        rec = {c: r.get(c) for c in _BASE_COLS}
        rec["Reason"] = ", ".join(dict.fromkeys(reasons))
        rec["Feld"] = "Address"
        rec["Alt"] = None if addr_raw is None or (not isinstance(addr_raw, str) and pd.isna(addr_raw)) else str(addr_raw)
        rec["Neu"] = neu
        rec["Kategorie"] = kat
        rec["Aktion"] = aktion
        rec["Confidence"] = conf
        out.append(rec)

    return out
