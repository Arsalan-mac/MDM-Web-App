"""Zerlegung: splits `Mandant.Address` into SAP's ADRC target fields.

Ported from the original app's sap_address_module.py (its regex parser and
length-enforcement logic only - the pure functions below are carried over
essentially unchanged, same regexes, same tiered strategy). A staged regex
parser handles standard cases (T0 PO box, T1 house number at the end, T2
house number at the front); complex cases (T3) optionally go to a Claude
Haiku batch call, with the regex best-effort kept as a fallback if the LLM
is unavailable or its answer doesn't validate. All length limits are always
enforced in code, never left to the LLM (see `_finalize`).

Deliberately NOT ported (see docs/ROADMAP.md): the LLM result cache table
(SAP-CARP's Name Splitting doesn't persist one either - an in-memory dict
per run is enough here too) and `calibrate_against_sap_streets` (a QA tool
comparing parsed streets against a real SAP street-name export, no ported
stage consumes its output).
"""

import re
from dataclasses import dataclass

_RE_WS = re.compile(r"\s+")
_HAS_LETTER = re.compile(r"[^\W\d_]")

_LEN_STREET, _LEN_SUPPL, _LEN_HN, _LEN_BLDG = 60, 40, 10, 20

CONF_HIGH, CONF_MED, CONF_MANUAL = "hoch", "mittel", ""
ACTION_REPLACE = "ERSETZEN"
ACTION_MANUAL = "MANUELL"

_KI_TRIGGER_HINTS = ("Hausnummer am Anfang UND Ende", "Keine Hausnummer erkannt", "Gebäudeinfo >")

_M_POSTFACH = "T0_POSTFACH"
_M_NR_END = "T1_NR_HINTEN"
_M_NR_FRONT = "T2_NR_VORNE"
_M_T3_KI = "T3_KI"
_M_T3_REGEX = "T3_REGEX"

LLM_MODEL = "claude-haiku-4-5-20251001"
LLM_BATCH_SIZE = 25

# Countries where the house number conventionally comes BEFORE the street name.
_NUMBER_FIRST_COUNTRIES = {"US", "GB", "IE", "FR", "CA", "AU", "NZ", "SG", "HK", "MY", "ZA"}

_RE_POSTFACH = re.compile(
    r"(?i)\b(postfach|post\s*box|p\.?\s*o\.?\s*box|pob|"
    r"bo[iî]te\s+postale|casella\s+postale|apartado|skrytka(\s+pocztowa)?)\b"
)

# 'c/o Firma XY, <Rest>' - the c/o part moves into the supplements.
_RE_CO = re.compile(r"(?i)^(?P<co>c\s*/\s*o\.?\s+[^,]{2,60})\s*,\s*(?P<rest>.+)$")

# Parenthesized suffix: 'Tekniikantie 14 (Innopoli 2)'
_RE_PAREN = re.compile(r"^(?P<rest>.+?)\s*\((?P<par>[^()]{1,60})\)\s*[.,]?$")

# Unit marker (Singapore/Malaysia): '120 Robinson Road #09-01'
_RE_UNIT = re.compile(r"^(?P<rest>.+?)[\s,]+(?P<unit>#\s?\d{1,4}(?:-\d{1,4})?)\s*$")

# T1 - house number at the END, optional 'Nr./No.' prefix, ranges '12-14',
# letters '44A', slash forms '112/d'; eats a leading comma ('Via Trieste, 23')
_RE_NR_LAST = re.compile(
    r"^(?P<street>.+?)[\s,]+"
    r"(?:(?i:nr|no|n)[°.:]{0,2}\s*)?"
    r"(?P<hn>\d+\s?[a-zA-Z]?(?:\s*[-–/]\s*[0-9a-zA-Z]{1,4})*)"
    r"\s*[.,]?$"
)

# T2 - house number at the FRONT: '514 Henderson Street', '16/24 Underwood Street'
_RE_NR_FIRST = re.compile(r"^(?P<hn>\d+[a-zA-Z]?(?:\s*[-–/]\s*\d+[a-zA-Z]?)?)[\s,]+(?P<street>[^\d\s].*)$")

# A pure number segment for T3 pairs: 'Nr. 98', '23'
_RE_PURE_NR = re.compile(r"(?i)^(?:(?:nr|no|n)[°.:]{0,2}\s*)?\d+\s?[a-zA-Z]?(?:\s*[-–/]\s*[0-9a-zA-Z]{1,4})*\s*$")

_RE_NR_TOKEN = re.compile(r"(?i)^(nr|no|n)[°.:]{0,2}$")

# Building/floor/room keywords (DE/EN/IT/RO/TR/PL, from the original's data profile).
_BLDG_WORDS = frozenset(
    "gebäude gebaeude geb haus building bldg tower turm block blok "
    "floor etage etg stock stockwerk og eg ug dg kat piano etaj et room rm raum zimmer zi "
    "suite ste unit apt apartment office büro buero hala budynek mansion center centre "
    "plaza campus pavillon pavilion wing corp cladirea level lev "
    "top stiege stg tür tuer tor parz parzelle".split()
)
_RE_BLDG = re.compile(r"(?i)\b(" + "|".join(sorted(_BLDG_WORDS, key=len, reverse=True)) + r")(?=[\s\d.,:#/-]|$)")

# Austrian apartment/staircase/floor markers at the end: 'Gasse 3/Top 6.19',
# 'Platz 9/4. Stock', 'Straße 1, Stiege 2, Tür 5', 'Weg 12 Zi 533' -> BUILDING
_RE_AT_UNIT = re.compile(
    r"(?i)^(?P<rest>.+?\d[0-9a-z]*)\s*[,/]?\s*"
    r"(?P<unit>(?:(?:top|stiege|stg\.?|tür|tuer|zi\.?|zimmer|tor|parz\.?)\s*\.?\s*[0-9a-z][0-9a-z./-]{0,9}"
    r"(?:\s*[,/]?\s*(?:top|stiege|stg\.?|tür|tuer|zi\.?|tor)\s*\.?\s*[0-9a-z][0-9a-z./-]{0,9})*"
    r"|\d{1,2}\.\s*(?:stock|og|etage|dg|tor)))\s*$"
)

# 'Str.'/'str.' -> 'Straße' (DE/AT) resp. 'Strasse' (CH) - only at a word boundary.
_RE_STR_ABBR = re.compile(r"(?i)(?<=[a-zäöüß])str\.?(?=$|\s|-)|(?<=\s)str\.(?=$|\s)")

_RE_WORDS = re.compile(r"[^\W\d_]+")


def spell_out_street(street: str, country_code: str) -> str:
    """'Hauptstr. 5' -> 'Hauptstraße', 'Bahnhofstr' -> 'Bahnhofstraße'; CH -> 'Strasse'.
    Returns '' if there's nothing to change or the country isn't DE/AT/CH."""
    cc = (country_code or "").strip().upper()
    if cc not in ("DE", "AT", "CH") or not street:
        return ""
    full = "strasse" if cc == "CH" else "straße"

    def _rep(m):
        tok = m.group(0)
        return full.capitalize() if tok[0].isupper() else full

    new = _RE_STR_ABBR.sub(_rep, street)
    return new if new != street and len(new) <= _LEN_STREET else ""


@dataclass
class ParseResult:
    street: str = ""
    house_num: str = ""
    suppl1: str = ""
    suppl2: str = ""
    suppl3: str = ""
    building: str = ""
    method: str = ""
    confidence: str = ""
    hinweis: str = ""


def _distribute_street(street_text: str) -> tuple:
    """Word-boundary-preserving distribution over STREET(60)/STR_SUPPL1-3(40 each)."""
    parts = []
    text = _RE_WS.sub(" ", str(street_text)).strip()
    for limit in (_LEN_STREET, _LEN_SUPPL, _LEN_SUPPL, _LEN_SUPPL):
        if len(text) <= limit:
            parts.append(text)
            text = ""
        else:
            idx = text.rfind(" ", 0, limit + 1)
            if idx <= 0:
                idx = limit
            parts.append(text[:idx].strip())
            text = text[idx:].strip()
    return parts[0], parts[1], parts[2], parts[3], text


def _norm_hn(hn: str) -> str:
    """Normalize a house number: '12 - 14'->'12-14', '2 a'->'2a', '–'->'-'."""
    hn = _RE_WS.sub(" ", str(hn)).strip(" .,")
    hn = re.sub(r"\s*([-–/])\s*", r"\1", hn).replace("–", "-")
    hn = re.sub(r"(\d)\s+([a-zA-Z])$", r"\1\2", hn)
    return hn


def _valid_street(street_text: str) -> bool:
    """Is this a plausible street candidate? (has letters, isn't a bare 'Nr.'
    token, isn't made ONLY of building keywords like 'Block'/'Etaj')."""
    if not _HAS_LETTER.search(street_text):
        return False
    if _RE_NR_TOKEN.match(street_text.strip(" .")):
        return False
    words = [w.lower() for w in _RE_WORDS.findall(street_text)]
    if words and all(w in _BLDG_WORDS for w in words):
        return False
    return True


def _seg_street_parse(seg: str):
    """Try to parse a single segment as 'street + house number'."""
    m = _RE_NR_LAST.match(seg)
    if m and _valid_street(m.group("street")) and "," not in m.group("street"):
        return m.group("street"), m.group("hn")
    m = _RE_NR_FIRST.match(seg)
    if m and _valid_street(m.group("street")) and "," not in m.group("street"):
        return m.group("street"), m.group("hn")
    return None


def _finalize(
    street_core: str, supplements: list, hn: str, building: str, method: str, confidence: str, hints: list
) -> ParseResult:
    """Central length enforcement - applies to EVERY path (regex + LLM).

    STREET is reserved exclusively for the street core; extra segments
    (c/o, districts, building leftovers) fill the STR_SUPPL slots.
    """
    street_core = _RE_WS.sub(" ", str(street_core)).strip(" ,")
    supplements = [p.strip(" ,") for p in supplements if str(p).strip(" ,")]

    hn = _norm_hn(hn)
    if hn and not re.search(r"[0-9A-Za-z]", hn):
        hints.append(f"Hausnummer ohne Ziffern/Buchstaben ('{hn}') verworfen")
        hn = ""
        confidence = CONF_MANUAL
    if len(hn) > _LEN_HN:
        street_core = f"{street_core} {hn}".strip()
        hn = ""
        confidence = CONF_MANUAL
        hints.append(f"Hausnummer > {_LEN_HN} Zeichen — in STREET belassen")

    building = _RE_WS.sub(" ", str(building)).strip()
    if len(building) > _LEN_BLDG:
        supplements.append(building)
        hints.append(f"Gebäudeinfo > {_LEN_BLDG} Zeichen — in STR_SUPPL belassen")
        building = ""

    street, s1, s2, s3, core_rest = _distribute_street(street_core)
    slots = [s1, s2, s3]

    supp = ", ".join(supplements).strip(" ,")
    if core_rest:
        supp = f"{core_rest}, {supp}".strip(" ,") if supp else core_rest
    for i in range(3):
        if not supp:
            break
        if slots[i]:
            continue
        if len(supp) <= _LEN_SUPPL:
            slots[i], supp = supp, ""
        else:
            idx = supp.rfind(" ", 0, _LEN_SUPPL + 1)
            if idx <= 0:
                idx = _LEN_SUPPL
            slots[i] = supp[:idx].strip(" ,")
            supp = supp[idx:].strip(" ,")
    if supp:
        confidence = CONF_MANUAL
        hints.append(f"Adresse zu lang — Rest abgeschnitten: {supp}")

    return ParseResult(
        street=street,
        house_num=hn,
        suppl1=slots[0],
        suppl2=slots[1],
        suppl3=slots[2],
        building=building,
        method=method,
        confidence=confidence,
        hinweis="; ".join(hints),
    )


def _parse_t3(s: str, extra_parts: list, building: str, hints: list) -> ParseResult:
    """Regex best-effort for complex addresses (comma segments, building keywords)."""
    segs = [t.strip(" .,") for t in s.split(",") if t.strip(" .,")]

    bldg_candidates, street_segs = [], []
    for seg in segs:
        if _RE_BLDG.search(seg) and _seg_street_parse(seg) is None:
            bldg_candidates.append(seg)
        else:
            street_segs.append(seg)

    street, hn = "", ""
    used = set()
    for i in range(len(street_segs) - 1):
        if (
            _HAS_LETTER.search(street_segs[i])
            and _seg_street_parse(street_segs[i]) is None
            and _valid_street(street_segs[i])
            and _RE_PURE_NR.match(street_segs[i + 1])
        ):
            street = street_segs[i]
            hn = re.sub(r"(?i)^(?:nr|no|n)[°.:]{0,2}\s*", "", street_segs[i + 1]).strip()
            used.update({i, i + 1})
            break
    if not street:
        for i, seg in enumerate(street_segs):
            parsed = _seg_street_parse(seg)
            if parsed:
                street, hn = parsed
                used.add(i)
                break
    if not street:
        letter_segs = [(i, seg) for i, seg in enumerate(street_segs) if _HAS_LETTER.search(seg)]
        if letter_segs:
            i, street = max(letter_segs, key=lambda t: len(t[1]))
            used.add(i)
        hints.append("Keine Hausnummer erkannt")

    leftovers = [seg for i, seg in enumerate(street_segs) if i not in used]

    for cand in bldg_candidates:
        if not building and len(cand) <= _LEN_BLDG:
            building = cand
        else:
            leftovers.append(cand)
            if len(cand) > _LEN_BLDG:
                hints.append(f"Gebäudeinfo > {_LEN_BLDG} Zeichen — in STR_SUPPL belassen")

    confidence = CONF_MED if hn else CONF_MANUAL
    supplements = extra_parts + leftovers
    if not street:
        street = supplements.pop(0) if supplements else s
    return _finalize(street, supplements, hn, building, _M_T3_REGEX, confidence, hints)


def parse_address(address: str, country_code: str = "") -> ParseResult:
    """Entry point: normalizes, classifies T0->T1/T2->T3, enforces lengths."""
    s = _RE_WS.sub(" ", str(address or "")).strip().strip(" ,;")
    if not s:
        return ParseResult(method=_M_T3_REGEX, confidence=CONF_MANUAL, hinweis="Adresse leer")

    hints, extra_parts, building = [], [], ""
    degraded = False

    m = _RE_AT_UNIT.match(s)
    if m and not _RE_POSTFACH.search(s):
        unit = _RE_WS.sub(" ", m.group("unit")).strip(" ,/")
        s = m.group("rest").strip(" ,/")
        if len(unit) <= _LEN_BLDG:
            building = unit
            hints.append("Wohnungs-/Stockangabe als BUILDING")
        else:
            extra_parts.append(unit)
            hints.append("Wohnungs-/Stockangabe in STR_SUPPL")
        degraded = True

    s = re.sub(r"(\.)(\d)", r"\1 \2", s)

    if _RE_POSTFACH.search(s):
        return _finalize(s, [], "", "", _M_POSTFACH, CONF_HIGH, ["Postfach-Adresse — komplett in STREET"])

    m = _RE_CO.match(s)
    if m:
        extra_parts.append(m.group("co").strip())
        s = m.group("rest").strip()
        hints.append("c/o-Zusatz in STR_SUPPL")
        degraded = True

    m = _RE_PAREN.match(s)
    if m:
        par = m.group("par").strip()
        s = m.group("rest").strip()
        if len(par) <= _LEN_BLDG:
            building = par
            hints.append("Klammerzusatz als BUILDING")
        else:
            extra_parts.append(par)
            hints.append(f"Klammerzusatz > {_LEN_BLDG} Zeichen — in STR_SUPPL")
        degraded = True

    m = _RE_UNIT.match(s)
    if m:
        unit = m.group("unit").replace(" ", "")
        s = m.group("rest").strip(" ,")
        if not building and len(unit) <= _LEN_BLDG:
            building = unit
            hints.append("Unit-Nummer als BUILDING")
        else:
            extra_parts.append(unit)
        degraded = True

    m_end = _RE_NR_LAST.match(s)
    if m_end and (not _valid_street(m_end.group("street")) or "," in m_end.group("street")):
        m_end = None
    m_front = _RE_NR_FIRST.match(s)
    if m_front and (not _valid_street(m_front.group("street")) or "," in m_front.group("street")):
        m_front = None

    if m_end and m_front:
        cc = (country_code or "").strip().upper()
        chosen = m_front if cc in _NUMBER_FIRST_COUNTRIES else m_end
        method = _M_NR_FRONT if chosen is m_front else _M_NR_END
        hints.append("Hausnummer am Anfang UND Ende möglich — per Länderkennung entschieden")
        return _finalize(chosen.group("street"), extra_parts, chosen.group("hn"), building, method, CONF_MED, hints)
    if m_end or m_front:
        chosen = m_end or m_front
        method = _M_NR_END if chosen is m_end else _M_NR_FRONT
        confidence = CONF_MED if degraded else CONF_HIGH
        return _finalize(chosen.group("street"), extra_parts, chosen.group("hn"), building, method, confidence, hints)

    return _parse_t3(s, extra_parts, building, hints)


def needs_llm(r: ParseResult) -> bool:
    """LLM scope: unparsable (T3) plus regex-uncertain cases."""
    if r.method == _M_T3_REGEX or r.confidence == CONF_MANUAL:
        return True
    return r.confidence == CONF_MED and any(h in (r.hinweis or "") for h in _KI_TRIGGER_HINTS)


_RE_DIGIT_RUN = re.compile(r"\d+")
_RE_ALNUM_TOKEN = re.compile(r"[^\W_]{2,}")


def _validate_llm_parts(original: str, street: str, hn: str, building: str, supplement: str) -> bool:
    """Is the LLM output plausible? (a) every digit run from the original
    survives, (b) no invented digits, (c) output tokens come from the
    original (translating/hallucinating is rejected)."""
    combined = " ".join([street, hn, building, supplement])
    orig_norm = _RE_WS.sub(" ", str(original)).lower()
    comb_digits = _RE_DIGIT_RUN.findall(combined)
    for d in _RE_DIGIT_RUN.findall(original):
        if d not in combined:
            return False
    for d in comb_digits:
        if d not in original:
            return False
    for tok in _RE_ALNUM_TOKEN.findall(combined):
        if tok.lower() not in orig_norm:
            return False
    return True


def _llm_result_from_parts(street: str, hn: str, building: str, supplement: str) -> ParseResult:
    supplements = [supplement] if supplement else []
    return _finalize(street, supplements, hn, building, _M_T3_KI, CONF_MED, ["KI-geparst"])


async def llm_parse_batch(client, items: list[tuple[str, str]]) -> dict[str, ParseResult]:
    """Sends complex addresses to Claude in batches. Returns {address:
    ParseResult} - only for validated answers; everything else keeps the
    regex result (see `needs_llm`/the caller's fallback)."""
    results: dict[str, ParseResult] = {}
    seen: set[str] = set()
    todo: list[tuple[str, str]] = []
    for addr, country in items:
        if addr in seen:
            continue
        seen.add(addr)
        todo.append((addr, country))

    chunks = [todo[i : i + LLM_BATCH_SIZE] for i in range(0, len(todo), LLM_BATCH_SIZE)]
    for chunk in chunks:
        numbered = "\n".join(f"{i + 1}. [{c or '??'}] {a}" for i, (a, c) in enumerate(chunk))
        prompt = (
            "Zerlege die folgenden Adressen (Länderkennung in eckigen Klammern) "
            "in SAP-Adressfelder.\n"
            "Antworte NUR mit nummerierten Zeilen im Format:\n"
            "N. STREET|HOUSE_NUM1|BUILDING|SUPPLEMENT\n\n"
            "Regeln:\n"
            "- STREET: Straßenname OHNE Hausnummer\n"
            "- HOUSE_NUM1: nur die Hausnummer (max 10 Zeichen), ohne 'Nr.'/'No.'-Präfix\n"
            "- BUILDING: Gebäude-/Block-/Etagen-/Raum-Angabe (max 20 Zeichen), sonst leer\n"
            "- SUPPLEMENT: alle übrigen Adressbestandteile, sonst leer\n"
            "- Verwende AUSSCHLIESSLICH Text aus der Original-Adresse — nichts "
            "erfinden, nichts übersetzen, nichts weglassen.\n\n" + numbered
        )
        try:
            msg = await client.messages.create(
                model=LLM_MODEL,
                max_tokens=LLM_BATCH_SIZE * 80,
                messages=[{"role": "user", "content": prompt}],
            )
            text = next((b.text for b in msg.content if b.type == "text"), "")
            for line in text.strip().splitlines():
                line = line.strip()
                dot_pos = line.find(". ")
                if dot_pos == -1:
                    continue
                try:
                    idx = int(line[:dot_pos]) - 1
                except ValueError:
                    continue
                if idx < 0 or idx >= len(chunk):
                    continue
                parts = [p.strip() for p in line[dot_pos + 2 :].split("|")]
                if len(parts) < 2:
                    continue
                parts += [""] * (4 - len(parts))
                street, hn, building, supplement = parts[:4]
                addr = chunk[idx][0]
                if not _validate_llm_parts(addr, street, hn, building, supplement):
                    continue
                results[addr] = _llm_result_from_parts(street, hn, building, supplement)
        except Exception:
            pass  # Batch failed -> affected addresses keep their regex result.
    return results
