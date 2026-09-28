"""Pure name-splitting helpers - given a single free-text name (a natural
person's name, possibly still sitting in a CompanyName-shaped field), split
it into (first_name, last_name). Two-token and comma-format names are
split deterministically via `nameparser`; ambiguous 3+-token names with no
title fall back to Claude Haiku, batched, with a plain first-token/rest
split if the LLM isn't configured or the call fails.

Originally written for SAP-CARP-Ueberschreibung's Name Splitting step
(app/cleansing/sap_carp_service.py, which re-exports these under its own
old private names so its existing tests keep working unchanged) and reused
as-is by the Mapping/Transform Studio's "name_split" field kind
(app/cleansing/mapping_service.py) - the same logic, not a fixed-schema
reimplementation, since a name doesn't care what table it came from.
"""

from anthropic import AsyncAnthropic
from nameparser import HumanName

NAME_SPLIT_MODEL = "claude-haiku-4-5-20251001"
NAME_SPLIT_BATCH_SIZE = 50


def name_needs_llm(name: str) -> str | None:
    name = name.strip()
    if not name or "," in name:
        return None
    n = HumanName(name)
    if n.title:
        return None
    tokens = [t for t in " ".join(filter(None, [n.first, n.middle, n.last])).split() if t]
    return " ".join(tokens) if len(tokens) >= 3 else None


def split_name(name: str, llm_cache: dict[str, dict] | None = None) -> dict:
    llm_cache = llm_cache or {}
    name = name.strip()
    if not name:
        return {"first_name": "", "last_name": "", "method": "unklar"}

    if "," in name:
        n = HumanName(name)
        given = " ".join(filter(None, [n.first, n.middle])).strip()
        return {"first_name": given, "last_name": n.last, "method": "komma"}

    n = HumanName(name)
    tokens = [t for t in " ".join(filter(None, [n.first, n.middle, n.last])).split() if t]
    if not tokens:
        return {"first_name": "", "last_name": "", "method": "unklar"}
    if len(tokens) == 1:
        return {"first_name": "", "last_name": tokens[0], "method": "unklar"}

    had_title = bool(n.title)
    if not had_title and len(tokens) >= 3:
        token_name = " ".join(tokens)
        if token_name in llm_cache:
            return llm_cache[token_name]
        # No LLM result available (not configured, or this call failed) -
        # same first-token/rest fallback the original app uses on an LLM error.
        return {"first_name": tokens[0], "last_name": " ".join(tokens[1:]), "method": "unklar"}

    method = "nameparser-titel" if had_title else "2-token"
    return {"first_name": " ".join(tokens[:-1]), "last_name": tokens[-1], "method": method}


async def llm_split_batch(client: AsyncAnthropic, names: list[str]) -> dict[str, dict]:
    cache: dict[str, dict] = {}
    chunks = [names[i : i + NAME_SPLIT_BATCH_SIZE] for i in range(0, len(names), NAME_SPLIT_BATCH_SIZE)]
    for chunk in chunks:
        numbered = "\n".join(f"{i + 1}. {n}" for i, n in enumerate(chunk))
        prompt = (
            "Trenne diese deutschen Namen in Vorname und Nachname.\n"
            "Antworte NUR mit nummerierten Zeilen im Format: N. VORNAME|NACHNAME\n"
            "Keine weiteren Erklärungen.\n\n" + numbered
        )
        try:
            msg = await client.messages.create(
                model=NAME_SPLIT_MODEL,
                max_tokens=NAME_SPLIT_BATCH_SIZE * 25,
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
                rest = line[dot_pos + 2 :]
                if "|" in rest:
                    vorname, nachname = rest.split("|", 1)
                    cache[chunk[idx]] = {"first_name": vorname.strip(), "last_name": nachname.strip(), "method": "llm"}
        except Exception:
            pass  # Falls through to split_name's per-name "unklar" fallback.
    return cache
