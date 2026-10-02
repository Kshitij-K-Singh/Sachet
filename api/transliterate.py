"""Urdu-script to Devanagari transliteration.

Why this exists: Whisper transcribes Hindi speech correctly at the word
level but often emits Perso-Arabic (Urdu) script instead of Devanagari.
Our rubric patterns and our users read Devanagari, so the pipeline
normalizes script after transcription. Latin and Devanagari pass through.

Method: deterministic character rules (aspirates, gemination, digraphs)
plus a small correction dictionary for high-value finance words where
Urdu underspecifies vowels (short vowels are unwritten in Urdu).
Only whole-word corrections apply, so running text cannot be corrupted.
"""

from __future__ import annotations

import re

# Base consonant/vowel map. Position-sensitive letters (ا ہ ی و ع) are
# handled in code below, not here.
_BASE = {
    "آ": "आ", "ب": "ब", "پ": "प", "ت": "त", "ٹ": "ट", "ث": "स",
    "ج": "ज", "چ": "च", "ح": "ह", "خ": "ख", "د": "द", "ڈ": "ड",
    "ذ": "ज़", "ر": "र", "ڑ": "ड़", "ز": "ज़", "ژ": "झ", "س": "स",
    "ش": "श", "ص": "स", "ض": "ज़", "ط": "त", "ظ": "ज़", "غ": "ग़",
    "ف": "फ", "ق": "क़", "ک": "क", "گ": "ग", "ل": "ल", "م": "म",
    "ن": "न", "ں": "ं",
    "ے": "े", "ۓ": "ै",
    "ء": "अ", "ۃ": "त",
}

_ASPIRATE = {
    "ب": "भ", "پ": "फ", "ت": "थ", "ٹ": "ठ", "ج": "झ", "چ": "छ",
    "د": "ध", "ڈ": "ढ", "ک": "ख", "گ": "घ", "م": "म्ह", "ن": "न्ह",
    "ل": "ल्ह", "ر": "ढ़", "و": "व्ह",
}

# Whole-word patches for finance-critical words. Seeded from real Whisper
# base-model output on Hindi finfluencer-style speech (Oct 2026).
def _build_corrections() -> dict[str, str]:
    raw = {
        "मनाफा": "मुनाफा",
        "मनाफे": "मुनाफे",
        "पैसह": "पैसा",
        "पैसे": "पैसे",
        "और": "और",
        "ग्रोप": "ग्रुप",
        "गरोप": "ग्रुप",
        "हमारह": "हमारा",
        "अभि": "अभी",
        "तिन": "तीन",
        "दिन": "दिन",
        "दन": "दिन",
        "पीसा": "पैसा",
        "दबल": "डबल",
        "परीमीम": "प्रीमियम",
    }
    return raw


# Bigram patches: safe only as pairs (e.g. bare जोन can mean "zone").
_BIGRAMS = {
    "जोन करें": "जॉइन करें",
    "जोन करो": "जॉइन करो",
}


_CORRECTIONS = _build_corrections()

_URDU_BLOCK = re.compile(r"[\u0600-\u06FF]+")


def _transliterate_token(token: str) -> str:
    out: list[str] = []
    chars = list(token)
    n = len(chars)
    i = 0
    prev_consonant = ""
    while i < n:
        ch = chars[i]
        nxt = chars[i + 1] if i + 1 < n else ""

        # Aspirate: consonant + do-chashmi he.
        if nxt == "ھ" and ch in _ASPIRATE:
            out.append(_ASPIRATE[ch])
            prev_consonant = ""
            i += 2
            continue
        if nxt == "ھ":
            out.append(_BASE.get(ch, ch))
            out.append("्ह")
            prev_consonant = ""
            i += 2
            continue
        # Tashdid: geminate previous consonant.
        if ch == "ّ":
            if prev_consonant:
                out.append("्" + prev_consonant)
            i += 1
            continue
        # Vowel signs: zer/pesh disambiguate, zabar/jazm drop.
        if ch == "ِ":
            out.append("ि")
            i += 1
            continue
        if ch == "ُ":
            out.append("ु")
            i += 1
            continue
        if ch in ("َ", "ْ", "ٰ"):
            i += 1
            continue
        # Digraphs with noon-ghunna.
        if ch == "ی" and nxt == "ں":
            out.append("ें")
            i += 2
            continue
        if ch == "و" and nxt == "ں":
            out.append("ों")
            i += 2
            continue
        if ch == "ا":
            out.append("अ" if i == 0 else "ा")
            prev_consonant = ""
            i += 1
            continue
        if ch == "ہ":
            out.append("ह" if i == 0 else "ा")
            prev_consonant = ""
            i += 1
            continue
        if ch == "ی":
            out.append("ी")
            prev_consonant = ""
            i += 1
            continue
        if ch == "و":
            out.append("ो")
            prev_consonant = ""
            i += 1
            continue
        if ch == "ع":
            if i == 0:
                out.append("अ")
            prev_consonant = ""
            i += 1
            continue
        if ch in _BASE:
            # Gemination: doubled consonant -> C + halant + C.
            if ch == prev_consonant:
                out.append("्" + _BASE[ch])
            else:
                out.append(_BASE[ch])
                prev_consonant = ch if ch not in ("ں",) else ""
            i += 1
            continue
        out.append(ch)
        prev_consonant = ""
        i += 1
    return "".join(out)


def transliterate(text: str) -> str:
    """Map every Perso-Arabic-script token to Devanagari; leave the rest."""

    def fix(match: re.Match) -> str:
        token = match.group(0)
        mapped = _transliterate_token(token)
        return _CORRECTIONS.get(mapped, mapped)

    out = _URDU_BLOCK.sub(fix, text)
    for src, dst in _BIGRAMS.items():
        out = out.replace(src, dst)
    return out
