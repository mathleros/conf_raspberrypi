"""Prétraitement déterministe des transcriptions vocales avant interprétation.

Porté depuis `scripts/test/eval_prompt_plan.py` ; `preprocess` gère en plus les durées et
distances composées (« 1 minute 30 secondes », « 1 mètre 50 »). Un petit LLM convertit mal les
nombres en lettres, on lui envoie donc un texte déjà normalisé (nombres en chiffres,
minutes -> secondes, mètres -> centimètres).
"""

from __future__ import annotations

import re

_UNITS = {
    "zéro": 0, "zero": 0, "un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5,
    "six": 6, "sept": 7, "huit": 8, "neuf": 9, "dix": 10, "onze": 11, "douze": 12, "treize": 13,
    "quatorze": 14, "quinze": 15, "seize": 16, "dix-sept": 17, "dix-huit": 18, "dix-neuf": 19,
}
_TENS = {"vingt": 20, "vingts": 20, "trente": 30, "quarante": 40, "cinquante": 50, "soixante": 60}
_UNIT_WORDS = {
    "mètre", "mètres", "metre", "metres", "centimètre", "centimètres", "centimetre", "centimetres",
    "cm", "m", "seconde", "secondes", "minute", "minutes", "degré", "degrés", "degre", "degres",
}


def _tokens(text: str) -> list[str]:
    text = text.lower().replace("’", "'")
    text = re.sub(r"\b([dlcjnmst])'(?=\w)", r"\1' ", text)  # d'un -> d' un
    return [t for t in re.split(r"[\s\-,;.!?]+", text) if t]


def fr_numbers_to_digits(text: str) -> str:
    """Remplace les nombres français en lettres par des chiffres (« un/une » seulement devant une unité)."""
    toks = _tokens(text)
    out: list[str] = []
    i = 0
    while i < len(toks):
        tok = toks[i]
        starts = tok in _UNITS or tok in _TENS or tok in ("cent", "cents", "mille")
        if not starts:
            out.append(tok)
            i += 1
            continue
        if tok in ("un", "une") and not (i + 1 < len(toks) and toks[i + 1] in _UNIT_WORDS):
            out.append(tok)
            i += 1
            continue
        total = cur = 0
        j, prev, consumed = i, None, 0
        while j < len(toks):
            t = toks[j]
            if t == "et" and consumed and j + 1 < len(toks) and (toks[j + 1] in _UNITS or toks[j + 1] in _TENS):
                j += 1
                continue
            if t in _UNITS:
                v = _UNITS[t]
                m = cur % 100
                ok = (
                    (m == 0 and not (consumed and prev in _UNITS))
                    or (m in (20, 30, 40, 50, 60, 70, 80, 90) and v < 10)
                    or (m in (60, 80) and 10 <= v < 20)
                    or (m == 10 and 7 <= v <= 9)
                )
                if t in ("un", "une") and consumed == 0:
                    ok = True
                if not ok:
                    break
                cur += v
            elif t in _TENS:
                if t in ("vingt", "vingts") and prev == "quatre" and cur % 10 == 4:
                    cur = cur - 4 + 80
                elif cur % 100 == 0:
                    cur += _TENS[t]
                else:
                    break
            elif t in ("cent", "cents"):
                cur = (cur or 1) * 100 if cur < 100 else cur
            elif t == "mille":
                total += (cur or 1) * 1000
                cur = 0
            else:
                break
            prev = t
            consumed += 1
            j += 1
        out.append(str(total + cur))
        i = j
    return " ".join(out)


_COMPOUND_DURATION_RE = re.compile(r"\b(\d+)\s+minutes?\s+(?:et\s+)?(\d+)\s+secondes?\b")
# « N mètre(s) [et] M [centimètre(s)] », M sur 1 ou 2 chiffres ; sans « centimètres », M ne doit pas
# être suivi d'une autre unité (« 1 mètre et 2 secondes » n'est pas une distance composée).
_COMPOUND_DISTANCE_RE = re.compile(
    r"\b(\d+)\s+m[eè]tres?\s+(?:et\s+)?(\d{1,2})"
    r"(?:\s+(?:centim[eè]tres?|cm)\b"
    r"|(?!\d|\s+(?:secondes?|minutes?|degr[eé]s?|m[eè]tres?|m|fois|tours?)\b))"
)


def preprocess(text: str) -> str:
    """Prétraitement déterministe avant le LLM : nombres en chiffres, minutes -> secondes, mètres -> cm.

    Les formes composées (« 1 minute 30 secondes », « 1 mètre 50 ») sont converties avant les formes simples.
    """
    t = fr_numbers_to_digits(text)
    t = _COMPOUND_DURATION_RE.sub(lambda m: f"{int(m.group(1)) * 60 + int(m.group(2))} secondes", t)
    t = _COMPOUND_DISTANCE_RE.sub(lambda m: f"{int(m.group(1)) * 100 + int(m.group(2))} centimètres", t)
    t = re.sub(r"\b(\d+)\s+minutes?\b", lambda m: f"{int(m.group(1)) * 60} secondes", t)
    t = re.sub(r"\b(\d+)\s+m[eè]tres?\b", lambda m: f"{int(m.group(1)) * 100} centimètres", t)
    return t
