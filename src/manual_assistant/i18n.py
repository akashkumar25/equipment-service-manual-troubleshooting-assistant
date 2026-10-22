"""Language handling: detect the question language, answer in it, bridge to English manuals.

Manuals are usually English while technicians ask in their own language. Three
small, dependency-free pieces make that work on any CPU:

* ``detect_language`` - stop-word voting over a handful of common languages.
* ``expand_query`` - appends English equivalents of common service terms, so
  BM25 can match an English manual from a German/French/Spanish question
  (the dense embedder can be switched to a multilingual model for more recall).
* ``LABELS`` - localized wording for the offline (no-LLM) answer.
"""

from __future__ import annotations

import re

LANGUAGE_NAMES = {
    "en": "English",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
}

_STOPWORDS = {
    "en": "the is are what how does do to of and for on in with my it when why can i a an fix check should",
    "de": "der die das ist sind was wie ein eine und für auf mit nicht wenn warum kann ich muss ich zu den dem bedeutet",
    "fr": "le la les est sont quel quelle comment un une et pour sur avec pas quand pourquoi puis je que signifie du des",
    "es": "el la los las es son qué que cómo un una y para en con no cuando por puedo significa del de se",
    "it": "il lo la gli le è sono cosa come un una e per su con non quando perché posso significa del di",
    "pt": "o os as é são qual como um uma e para em com não quando por que posso significa do da de",
    "nl": "de het een is zijn wat hoe en voor op met niet wanneer waarom kan ik betekent van",
}
_STOP_SETS = {lang: set(words.split()) for lang, words in _STOPWORDS.items()}
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)


def detect_language(text: str, default: str = "en") -> str:
    """Return a language code from ``LANGUAGE_NAMES``; ``default`` if there is no signal."""
    words = [w.lower() for w in _WORD.findall(text)]
    if not words:
        return default
    scores = {lang: sum(w in stops for w in words) for lang, stops in _STOP_SETS.items()}
    # Umlauts and ß are a strong German cue that stop words alone can miss.
    if re.search(r"[äöüß]", text.lower()):
        scores["de"] += 1
    best = max(scores, key=lambda lang: (scores[lang], lang == default))
    return best if scores[best] > 0 else default


# Service vocabulary -> English terms used in manuals.
_GLOSSARY: dict[str, dict[str, str]] = {
    "de": {
        "hydrauliköl": "hydraulic oil", "hydraulik": "hydraulic", "temperatur": "temperature",
        "druck": "pressure", "zu hoch": "too high", "zu niedrig": "too low",
        "heiß": "hot", "überhitzt": "overheating", "motor": "engine", "fehler": "fault",
        "fehlercode": "fault code", "lenkung": "steering", "schwer": "heavy",
        "schaufel": "bucket", "hebt": "lifts", "langsam": "slowly", "bremse": "brake",
        "kühlmittel": "coolant", "kühler": "radiator", "filter": "filter", "sensor": "sensor",
        "batterie": "battery", "kraftstoff": "fuel", "getriebe": "transmission",
        "öl": "oil", "leck": "leak", "undicht": "leak", "pumpe": "pump",
        "ventil": "valve", "schlauch": "hose", "kette": "track", "reifen": "tyre",
    },
    "fr": {
        "huile hydraulique": "hydraulic oil", "hydraulique": "hydraulic",
        "température": "temperature", "pression": "pressure", "trop élevée": "too high",
        "trop basse": "too low", "chaud": "hot", "moteur": "engine", "défaut": "fault",
        "direction": "steering", "lourde": "heavy", "godet": "bucket", "frein": "brake",
        "liquide de refroidissement": "coolant", "radiateur": "radiator", "capteur": "sensor",
        "batterie": "battery", "carburant": "fuel", "transmission": "transmission",
        "huile": "oil", "fuite": "leak", "pompe": "pump", "soupape": "valve",
        "flexible": "hose", "chenille": "track", "pneu": "tyre",
    },
    "es": {
        "aceite hidráulico": "hydraulic oil", "hidráulico": "hydraulic",
        "temperatura": "temperature", "presión": "pressure", "demasiado alta": "too high",
        "demasiado baja": "too low", "caliente": "hot", "motor": "engine", "fallo": "fault",
        "dirección": "steering", "pesada": "heavy", "cucharón": "bucket", "freno": "brake",
        "refrigerante": "coolant", "radiador": "radiator", "sensor": "sensor",
        "batería": "battery", "combustible": "fuel", "transmisión": "transmission",
        "aceite": "oil", "fuga": "leak", "bomba": "pump", "válvula": "valve",
        "manguera": "hose", "oruga": "track", "neumático": "tyre",
    },
}


def expand_query(question: str, lang: str) -> str:
    """Append English equivalents of known terms; English questions are returned unchanged."""
    glossary = _GLOSSARY.get(lang)
    if not glossary:
        return question
    low = question.lower()
    extra: list[str] = []
    # Longest phrases first so "huile hydraulique" wins over "huile".
    for term in sorted(glossary, key=len, reverse=True):
        if term in low:
            extra.append(glossary[term])
    return question if not extra else f"{question} {' '.join(dict.fromkeys(extra))}"


LABELS = {
    "en": {"see": "See", "none": "No relevant manual pages found."},
    "de": {"see": "Siehe", "none": "Keine passenden Handbuchseiten gefunden."},
    "fr": {"see": "Voir", "none": "Aucune page de manuel pertinente trouvée."},
    "es": {"see": "Ver", "none": "No se encontraron páginas de manual relevantes."},
    "it": {"see": "Vedi", "none": "Nessuna pagina del manuale pertinente trovata."},
    "pt": {"see": "Ver", "none": "Nenhuma página de manual relevante encontrada."},
    "nl": {"see": "Zie", "none": "Geen relevante handleidingpagina's gevonden."},
}


def label(lang: str, key: str) -> str:
    return LABELS.get(lang, LABELS["en"])[key]
