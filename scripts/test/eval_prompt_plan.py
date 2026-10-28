#!/usr/bin/env python3
"""Évalue le prompt système du planificateur LLM (étape 8) sur un llama-server local.

Usage :
    python3 eval_prompt_plan.py                       # serveur sur 127.0.0.1:8080
    python3 eval_prompt_plan.py --repeat 3            # latence plus fiable
    python3 eval_prompt_plan.py --only usecase,carre  # quelques cas
    python3 eval_prompt_plan.py --prompt-file p.txt   # tester une variante du prompt
    python3 eval_prompt_plan.py --no-response-format  # sans JSON contraint
    python3 eval_prompt_plan.py --schema              # sortie contrainte par schéma JSON
    python3 eval_prompt_plan.py --no-preprocess       # envoie le texte brut (nombres en lettres)
    python3 eval_prompt_plan.py --json-out rapport.json

Stdlib uniquement (pas de pip). Les phrases imitent la sortie de Vosk : minuscules,
sans ponctuation, nombres en toutes lettres.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
import urllib.error
import urllib.request

SYSTEM_PROMPT_PLAN = """Tu convertis une consigne vocale pour un robot en JSON strict, sans aucun texte autour.
Format : {"steps":[{"intent":"...","target":null,"parameters":{}}]}
Intents :
- move_forward, move_backward : parameters {"distance":cm} ou {"duration":secondes}
- turn_left, turn_right : parameters {"angle":degrés} ou {"duration":secondes}
- stop
- search_and_approach_object : target "red" ou "yellow", parameters {"stand_off_cm":cm}
- follow_object : target "red" ou "yellow", parameters {"stand_off_cm":cm,"duration_s":secondes}
- follow_red_ball : target "red_ball"
- avoid_obstacle, spin_360, return_to_start
- move_square : parameters {"side":cm}
Règles : une étape par action, dans l'ordre. Les nombres sont déjà en chiffres, distances en centimètres, durées en secondes. Sans valeur donnée : avance/recule -> duration 1 ; tourne -> angle 90. jaune = "yellow", rouge = "red". Consigne impossible ou hors liste -> {"steps":[]}.
Exemples :
« cherche la balle jaune approche toi à 100 centimètres de la balle jaune puis suis la pendant 300 secondes » -> {"steps":[{"intent":"search_and_approach_object","target":"yellow","parameters":{"stand_off_cm":100}},{"intent":"follow_object","target":"yellow","parameters":{"stand_off_cm":100,"duration_s":300}}]}
« avance de 50 centimètres puis tourne à gauche de 45 degrés » -> {"steps":[{"intent":"move_forward","target":null,"parameters":{"distance":50}},{"intent":"turn_left","target":null,"parameters":{"angle":45}}]}
« avance » -> {"steps":[{"intent":"move_forward","target":null,"parameters":{"duration":1}}]}
« suis la balle rouge » -> {"steps":[{"intent":"follow_red_ball","target":"red_ball","parameters":{}}]}
« fais un salto arrière » -> {"steps":[]}"""

_UNITS = {"zéro":0,"zero":0,"un":1,"une":1,"deux":2,"trois":3,"quatre":4,"cinq":5,"six":6,"sept":7,
          "huit":8,"neuf":9,"dix":10,"onze":11,"douze":12,"treize":13,"quatorze":14,"quinze":15,
          "seize":16,"dix-sept":17,"dix-huit":18,"dix-neuf":19}
_TENS = {"vingt":20,"vingts":20,"trente":30,"quarante":40,"cinquante":50,"soixante":60}
_UNIT_WORDS = {"mètre","mètres","metre","metres","centimètre","centimètres","centimetre","centimetres",
               "cm","m","seconde","secondes","minute","minutes","degré","degrés","degre","degres"}


def _tokens(text):
    text = text.lower().replace("’", "'")
    text = re.sub(r"\b([dlcjnmst])'(?=\w)", r"\1' ", text)   # d'un -> d' un
    return [t for t in re.split(r"[\s\-,;.!?]+", text) if t]


def fr_numbers_to_digits(text):
    toks = _tokens(text)
    out, i = [], 0
    while i < len(toks):
        tok = toks[i]
        starts = tok in _UNITS or tok in _TENS or tok in ("cent", "cents", "mille")
        if not starts:
            out.append(tok); i += 1; continue
        # « un/une » seul : nombre seulement s'il précède une unité de mesure
        if tok in ("un", "une") and not (i + 1 < len(toks) and toks[i + 1] in _UNIT_WORDS):
            out.append(tok); i += 1; continue
        total = cur = 0
        j, prev, consumed = i, None, 0
        while j < len(toks):
            t = toks[j]
            if t == "et" and consumed and j + 1 < len(toks) and (toks[j+1] in _UNITS or toks[j+1] in _TENS):
                j += 1; continue
            if t in ("un", "une") and consumed and cur % 100 == 0 and cur:   # « cent un »
                pass
            if t in _UNITS:
                v = _UNITS[t]
                m = cur % 100
                ok = (m == 0 and not (consumed and prev in _UNITS)) or (m in (20,30,40,50,60,70,80,90) and v < 10) \
                     or (m in (60, 80) and 10 <= v < 20) or (m == 10 and 7 <= v <= 9)
                if t in ("un","une") and consumed == 0:
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
                total += (cur or 1) * 1000; cur = 0
            else:
                break
            prev = t; consumed += 1; j += 1
        out.append(str(total + cur)); i = j
    return " ".join(out)


def preprocess(text):
    """Prétraitement déterministe avant le LLM : nombres en chiffres, minutes -> secondes, mètres -> cm."""
    t = fr_numbers_to_digits(text)
    t = re.sub(r"\b(\d+)\s+minutes?\b", lambda m: f"{int(m.group(1)) * 60} secondes", t)
    t = re.sub(r"\b(\d+)\s+m[eè]tres?\b", lambda m: f"{int(m.group(1)) * 100} centimètres", t)
    return t


ALLOWED_INTENTS = {
    "move_forward", "move_backward", "turn_left", "turn_right", "stop",
    "search_and_approach_object", "follow_object", "follow_red_ball",
    "avoid_obstacle", "spin_360", "move_square", "return_to_start",
    "contour_obstacle", "execute_path",
}
ANY = "any"  # le paramètre doit exister et être un nombre > 0


def S(intent, target=None, **p):
    return {"intent": intent, "target": target, "p": p}


# id, phrase (style Vosk), liste de plans acceptables
CASES = [
    ("usecase",
     "cherche la balle jaune approche toi à un mètre de la balle jaune puis suis la pendant cinq minutes",
     [[S("search_and_approach_object", "yellow", stand_off_cm=100),
       S("follow_object", "yellow", stand_off_cm=100, duration_s=300)]]),
    ("avance_tourne",
     "avance de cinquante centimètres puis tourne à gauche de quarante cinq degrés",
     [[S("move_forward", distance_cm=50), S("turn_left", angle=45)]]),
    ("recule_m", "recule de deux mètres", [[S("move_backward", distance_cm=200)]]),
    ("avance_nu", "avance",
     [[S("move_forward", duration=ANY)], [S("move_forward", distance_cm=ANY)]]),
    ("droite_nu", "tourne à droite",
     [[S("turn_right", angle=ANY)], [S("turn_right", duration=ANY)]]),
    ("stop", "arrête toi", [[S("stop")]]),
    ("stop_nu", "stop", [[S("stop")]]),
    ("halte", "halte", [[S("stop")]]),
    ("carre", "fais un carré de un mètre", [[S("move_square", side_cm=100)]]),
    ("spin", "fais un tour complet sur toi même",
     [[S("spin_360")], [S("turn_right", angle=360)], [S("turn_left", angle=360)]]),
    ("suis_rouge", "suis la balle rouge",
     [[S("follow_red_ball", "red_ball")], [S("follow_object", "red")]]),
    ("retour", "avance d'un mètre puis reviens au point de départ",
     [[S("move_forward", distance_cm=100), S("return_to_start")]]),
    ("hors_liste", "fais un salto arrière", [[]]),
    ("hors_liste_2", "chante une chanson", [[]]),
    ("hors_liste_3", "ouvre la porte du garage", [[]]),
    ("couleur_non_geree", "va chercher la balle bleue", [[]]),
    ("approche_50", "approche toi de la balle jaune à cinquante centimètres",
     [[S("search_and_approach_object", "yellow", stand_off_cm=50)]]),
    ("gauche_2s", "tourne à gauche pendant deux secondes",
     [[S("turn_left", duration=2)]]),
    ("avance_10s_stop", "avance pendant dix secondes puis arrête",
     # « puis arrête » est redondant : le runtime ajoute un stop en fin de plan
     [[S("move_forward", duration=10), S("stop")], [S("move_forward", duration=10)]]),
    ("suis_jaune_30s", "suis la balle jaune pendant trente secondes à deux mètres",
     [[S("follow_object", "yellow", stand_off_cm=200, duration_s=30)]]),
    # avoid_obstacle est peu fiable côté robot (rotations bloquées par l'obstacle) : [] accepté aussi
    ("evite", "évite l'obstacle", [[S("avoid_obstacle")], []]),
    ("trois_etapes",
     "avance de vingt centimètres puis recule de dix centimètres puis tourne à droite de quatre vingt dix degrés",
     [[S("move_forward", distance_cm=20), S("move_backward", distance_cm=10),
       S("turn_right", angle=90)]]),
    ("bruit_singulier", "avance de cinquante centimètre", [[S("move_forward", distance_cm=50)]]),
    ("cherche_seul", "cherche la balle jaune",
     [[S("search_and_approach_object", "yellow")]]),
    ("anglais", "go forward one meter", [[S("move_forward", distance_cm=100)]]),
    ("nombre_compose", "tourne à droite de quatre vingt dix degrés", [[S("turn_right", angle=90)]]),
    ("nombre_soixante", "avance de soixante et onze centimètres", [[S("move_forward", distance_cm=71)]]),
]


PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "steps": {
            "type": "array",
            "maxItems": 8,
            "items": {
                "type": "object",
                "properties": {
                    "intent": {"type": "string", "enum": [
                        "move_forward", "move_backward", "turn_left", "turn_right", "stop",
                        "search_and_approach_object", "follow_object", "follow_red_ball",
                        "avoid_obstacle", "spin_360", "move_square", "return_to_start"]},
                    "target": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "distance": {"type": "number"}, "duration": {"type": "number"},
                            "angle": {"type": "number"}, "stand_off_cm": {"type": "number"},
                            "duration_s": {"type": "number"}, "side": {"type": "number"},
                        },
                        "additionalProperties": False,
                    },
                },
                "required": ["intent"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["steps"],
    "additionalProperties": False,
}


def build_formats(no_response_format: bool, use_schema: bool):
    if no_response_format:
        return [None]
    if use_schema:
        return [
            {"type": "json_schema", "json_schema": {"name": "plan", "strict": True, "schema": PLAN_SCHEMA}},
            {"type": "json_object", "schema": PLAN_SCHEMA},
            {"type": "json_object"},
            None,
        ]
    return [{"type": "json_object"}, None]


# --------------------------------------------------------------------------- JSON


def parse_llm_json(content: str):
    """Même tolérance que _parse_llm_json_payload du runtime (backticks, ```json)."""
    cleaned = (content or "").strip()
    if not cleaned:
        return None
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned.split("\n", 1)[1].strip() if "\n" in cleaned else cleaned[4:].strip()
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _num(value):
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def canonical_params(params: dict) -> dict:
    """Ramène les paramètres du LLM à des clés comparables (cm, degrés, secondes)."""
    out = {}
    unit = str(params.get("unit", "cm")).strip().lower()
    to_cm = 100.0 if unit in {"m", "meter", "meters", "metre", "metres", "mètre", "mètres"} else 1.0
    for src, dst in (("distance", "distance_cm"), ("side", "side_cm")):
        v = _num(params.get(src))
        if v is not None:
            out[dst] = v * to_cm
    for key in ("angle", "duration", "stand_off_cm", "duration_s"):
        v = _num(params.get(key))
        if v is not None:
            out[key] = v
    return out


def schema_errors(steps: list) -> list[str]:
    errors = []
    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            errors.append(f"étape {i}: pas un objet")
            continue
        intent = step.get("intent") or step.get("name")
        params = step.get("parameters", {})
        if intent not in ALLOWED_INTENTS:
            errors.append(f"étape {i}: intent inconnu {intent!r}")
        if not isinstance(params, dict):
            errors.append(f"étape {i}: parameters n'est pas un objet (le runtime rejetterait TOUT le plan)")
            continue
        unit = params.get("unit")
        if unit is not None and str(unit) not in {"cm", "m", "degrees"}:
            errors.append(f"étape {i}: unité hors {{cm,m}} -> {unit!r} (traitée comme cm)")
        if intent in {"move_forward", "move_backward"} and not any(
            k in params for k in ("distance", "duration")
        ):
            errors.append(f"étape {i}: {intent} sans distance ni duration (mouvement continu)")
        for key in ("distance", "angle", "duration", "stand_off_cm", "duration_s", "side"):
            if key in params and _num(params[key]) is None:
                errors.append(f"étape {i}: {key} non numérique -> {params[key]!r}")
        target = step.get("target")
        if intent == "follow_red_ball" and target not in (None, "red_ball"):
            errors.append(f"étape {i}: follow_red_ball avec target {target!r} (rejeté par le validateur)")
        if intent in {"search_and_approach_object", "follow_object"} and target not in (
            None, "red", "yellow"
        ):
            errors.append(f"étape {i}: target {target!r} hors red/yellow")
    return errors


def step_matches(actual: dict, expected: dict) -> bool:
    intent = actual.get("intent") or actual.get("name")
    if intent != expected["intent"]:
        return False
    target = actual.get("target")
    if target in ("", "null", "none", "None"):
        target = None
    if (expected["target"] or None) != (target or None):
        return False
    params = actual.get("parameters") if isinstance(actual.get("parameters"), dict) else {}
    canon = canonical_params(params)
    for key, want in expected["p"].items():
        got = canon.get(key)
        if got is None:
            return False
        if want == ANY:
            if got <= 0:
                return False
        elif abs(got - float(want)) > 0.5:
            return False
    return True


def plan_matches(steps: list, expected_plan: list) -> bool:
    if len(steps) != len(expected_plan):
        return False
    return all(
        isinstance(a, dict) and step_matches(a, e) for a, e in zip(steps, expected_plan)
    )


# --------------------------------------------------------------------------- HTTP


def call_llm(url, system_prompt, text, *, model, max_tokens, formats, timeout):
    """`formats` : liste de response_format à essayer dans l'ordre (None = sans contrainte).
    On passe au suivant sur HTTP 400 (option non gérée par cette version de llama-server)."""
    base = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ],
        "temperature": 0.0,
        "max_tokens": max_tokens,
        "stream": False,
        "cache_prompt": True,
    }

    def post(body):
        req = urllib.request.Request(
            url, data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    started = time.perf_counter()
    data, used = None, 0
    for used, fmt in enumerate(formats):
        body = dict(base)
        if fmt:
            body["response_format"] = fmt
        try:
            data = post(body)
            break
        except urllib.error.HTTPError as exc:
            if exc.code == 400 and used < len(formats) - 1:
                continue
            raise
    elapsed = time.perf_counter() - started
    content = data["choices"][0]["message"]["content"]
    usage = data.get("usage") or {}
    return content, elapsed, usage, used


# --------------------------------------------------------------------------- main


def percentile(values, q):
    if not values:
        return float("nan")
    ordered = sorted(values)
    k = max(0, min(len(ordered) - 1, round(q * (len(ordered) - 1))))
    return ordered[k]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--url", default="http://127.0.0.1:8080/v1/chat/completions")
    ap.add_argument("--model", default="qwen2.5-1.5b")
    ap.add_argument("--max-tokens", type=int, default=160)
    ap.add_argument("--read-timeout", type=float, default=4.0,
                    help="seuil du runtime (4 s) : sert uniquement à compter les dépassements")
    ap.add_argument("--http-timeout", type=float, default=90.0)
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--only", default="", help="ids séparés par des virgules")
    ap.add_argument("--prompt-file", help="fichier texte contenant un prompt système alternatif")
    ap.add_argument("--no-response-format", action="store_true")
    ap.add_argument("--schema", action="store_true",
                    help="contraint la sortie avec un schéma JSON (repli auto si le serveur refuse)")
    ap.add_argument("--no-preprocess", action="store_true",
                    help="ne convertit pas les nombres en chiffres avant l'envoi")
    ap.add_argument("--json-out")
    args = ap.parse_args()

    prompt = SYSTEM_PROMPT_PLAN
    if args.prompt_file:
        with open(args.prompt_file, encoding="utf-8") as fh:
            prompt = fh.read().strip()

    only = {x.strip() for x in args.only.split(",") if x.strip()}
    cases = [c for c in CASES if not only or c[0] in only]
    if not cases:
        print("Aucun cas sélectionné.")
        return 2

    formats = build_formats(args.no_response_format, args.schema)
    print(f"Prompt système : {len(prompt)} caractères (~{round(len(prompt) / 3.3)} tokens estimés)")
    print(f"Serveur : {args.url} | cas : {len(cases)} x {args.repeat}\n")

    try:  # préchauffage : remplit le cache de prompt, non comptabilisé
        call_llm(args.url, prompt, "arrête toi", model=args.model, max_tokens=args.max_tokens,
                 formats=formats, timeout=args.http_timeout)
    except Exception as exc:
        print(f"Serveur injoignable ou erreur au préchauffage : {exc}")
        return 2

    rows, latencies, tps = [], [], []
    for case_id, text, plans in cases:
        for run in range(args.repeat):
            sent = text if args.no_preprocess else preprocess(text)
            row = {"id": case_id, "run": run, "text": text, "sent": sent}
            try:
                content, elapsed, usage, fb = call_llm(
                    args.url, prompt, sent, model=args.model, max_tokens=args.max_tokens,
                    formats=formats, timeout=args.http_timeout)
            except Exception as exc:
                row.update(status="ERREUR", detail=str(exc), latency=None)
                rows.append(row)
                print(f"[ERREUR] {case_id}: {exc}")
                continue

            parsed = parse_llm_json(content)
            steps = parsed.get("steps") if parsed else None
            row.update(latency=round(elapsed, 3), content=content,
                       completion_tokens=usage.get("completion_tokens"),
                       prompt_tokens=usage.get("prompt_tokens"), response_format_fallback=bool(fb),
                       response_format_index=fb)
            latencies.append(elapsed)
            if usage.get("completion_tokens") and elapsed > 0:
                tps.append(usage["completion_tokens"] / elapsed)

            if parsed is None:
                row.update(status="JSON_INVALIDE", detail="repli parseur local")
            elif not isinstance(steps, list):
                row.update(status="SANS_STEPS", detail="clé 'steps' absente ou non liste")
            else:
                errs = schema_errors(steps)
                ok = any(plan_matches(steps, p) for p in plans)
                # Hors périmètre attendu, mais le LLM a nommé une cible inconnue : le validateur
                # du runtime rejette le plan, ce qui est sans danger.
                safe_reject = (not ok and [] in plans and errs
                               and all("target" in e for e in errs))
                if safe_reject:
                    row.update(status="OK_VALIDATEUR", detail="rejeté par le validateur (sans danger)",
                               steps=steps)
                    rows.append(row)
                    print(f"[OK_VALIDATEUR ] {case_id:<18} {elapsed:6.2f}s  {'LENT' if elapsed > args.read_timeout else ''}")
                    continue
                # steps vide = repli sur le parseur local côté runtime (comportement attendu pour [])
                row.update(status="OK" if ok and not errs else ("SCHEMA" if ok else "ECART"),
                           detail="; ".join(errs) if errs else "",
                           steps=steps)
            rows.append(row)
            slow = " LENT" if elapsed > args.read_timeout else ""
            print(f"[{row['status']:<13}] {case_id:<18} {elapsed:6.2f}s{slow}  {row.get('detail', '')}")
            if row["status"] in {"ECART", "SCHEMA", "JSON_INVALIDE", "SANS_STEPS"}:
                print(f"    -> {(content or '').strip()[:300]}")

    total = len(rows)
    valid = sum(1 for r in rows if r["status"] in {"OK", "SCHEMA", "ECART"})
    ok = sum(1 for r in rows if r["status"] in {"OK", "OK_VALIDATEUR"})
    slow = sum(1 for r in latencies if r > args.read_timeout)
    print("\n=== Par cas (instable = résultats différents entre répétitions) ===")
    by_case = {}
    for r in rows:
        by_case.setdefault(r["id"], []).append(r["status"])
    for cid, sts in by_case.items():
        good = sum(1 for x in sts if x in {"OK", "OK_VALIDATEUR"})
        if good != len(sts):
            print(f"  {cid:<20} {good}/{len(sts)}  {'INSTABLE' if good else 'ÉCHEC'}  {sts}")
    print("\n=== Résumé ===")
    print(f"JSON valide avec 'steps' : {valid}/{total}")
    print(f"Plan correct + schéma OK : {ok}/{total} ({100 * ok / total:.0f} %)")
    if latencies:
        print(f"Latence : moy {statistics.mean(latencies):.2f}s | médiane {statistics.median(latencies):.2f}s"
              f" | p95 {percentile(latencies, 0.95):.2f}s | max {max(latencies):.2f}s")
        print(f"Au-dessus de {args.read_timeout:.0f}s (repli parseur local en prod) : {slow}/{len(latencies)}")
    if tps:
        print(f"Débit de génération : ~{statistics.mean(tps):.1f} tokens/s (approx., inclut l'évaluation du prompt)")
    ptok = [r["prompt_tokens"] for r in rows if r.get("prompt_tokens")]
    if ptok:
        print(f"Tokens de prompt (mesurés par le serveur) : ~{round(statistics.mean(ptok))}")
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump(rows, fh, ensure_ascii=False, indent=2)
        print(f"Rapport écrit : {args.json_out}")
    return 0 if ok == total else 1


if __name__ == "__main__":
    sys.exit(main())
