"""
Sachet (Sangyan Track E) — rubric + heuristic baseline analyzer.

This is the Day-1 explainable baseline: pure-Python keyword rules over a
FIXED rubric taxonomy. No ML model, no external API calls. Every claim
emitted quotes the input verbatim; anything we cannot verify is labelled
"cannot_verify" — never "false".

Rubric v1.0 (7 flags, weights in parentheses):
  1. unrealistic_returns (3) — guaranteed / doubling / 10x style promises
  2. risk_downplay      (2) — "no risk", "safe", "zero loss" language
  3. fake_authority     (2) — unverifiable insider / secret-source claims
  4. paid_service_cta   (2) — join group / app / paid service directives
  5. urgency_pressure   (1) — act-now / limited seats / last chance
  6. social_proof       (1) — testimonial / screenshot-profit as evidence
  7. missing_disclosure (1) — doc-level: risky content with no risk disclaimer

Caution score = sum of weights of flags present (doc-level, deduped).
  0-1  -> low    | education-leaning
  2-4  -> medium | mixed
  5+   -> high   | promotion-leaning

Classification:
  score == 0            -> education
  score >= 5            -> promotion
  2-4                   -> mixed
  score == 1            -> mixed, unless the single flag is only
                           missing_disclosure (then education with a nudge).

Claim types: return_promise | risk_denial | authority | urgency |
             testimonial | product_pitch | neutral_fact

SOURCES (verified Oct 1, 2026; see SOURCES below, not model memory):
  [S1] Advertisement code for Investment Advisers (IA) and Research
       Analysts (RA), SEBI/HO/MIRSD/MIRSD-PoD-2/P/CIR/2023/51,
       Apr 5 2023 (effective May 1, 2023). Defines advertisement as all
       communications by/on behalf of an IA/RA that may influence
       investment decisions; IAs/RAs must follow their code of conduct.
  [S2] Finfluencer association framework: SEBI Board decision Jun 27 2024,
       in force Aug 29 2024 via the Intermediaries (Amendment) Regulations
       2024; Oct 22 2024 circular directing regulated entities to end ties
       with unregistered advisers; Jan 29 2025 circular. Unregistered
       persons must not give advice/recommendations or make implicit or
       explicit claims of return/performance. Genuine investor education
       with no advice, recommendation, or return claim is excluded.
  [S3] Sixth Schedule, SEBI (Mutual Funds) Regulations, 1996
       (Advertisement Code): ads must be true, fair, and not misleading;
       no testimonials or rankings; mandatory standard warning
       "Mutual Fund investments are subject to market risks, read all
       scheme related documents carefully."
"""

from __future__ import annotations

import re

RUBRIC_VERSION = "rubric-v1.1"

DISCLAIMER = "This is an awareness tool, not investment advice."

# ---------------------------------------------------------------- patterns

# Each entry: (flag, claim_type, regex, human reason template)
# Keep patterns case-insensitive, English + Hinglish/Hindi-transliterated
# + Devanagari. Extended Oct 1 against the batch-1 dataset misses; every
# addition below fired on a real candidate miss, never added speculatively.
_PATTERNS: list[tuple[str, str, str, str]] = [
    (
        "unrealistic_returns",
        "return_promise",
        r"(guarantee\w*\s+(return|profit|income|doubling)|assured\s+returns?|"
        r"(assured|guaranteed)\s+(returns?|profits?|income)|"
        r"returns?\s+are\s+(assured|guaranteed)|"
        r"double\s+(your|the\s+)?money|10x|[2-9]x\b|tripl\w+|multibagger|"
        r"100\s?%\s*(return|profit|guarantee|sure)|"
        r"daily\s+profit|weekly\s+profit|fixed\s+profit|risk-?free\s+profit|"
        r"\d+\s?(?:%|percent)\s*(profit|returns?)\s+(every|per|a)\s+(week|month|day)|"
        r"turn\s+[\d,]+\s+into|into\s+\d*\s*(lakh|crore)|into\s+double|"
        r"guaranteed\s+\d|pakka\s+(profit|return|munaafa?)|double\s+paisa|"
        r"paisa\s+double|pes[ae]\s+(double|dubbal|dubble)|double\s+pes[ae]|"
        r"munaafa?\s+(pakka|guarantee)|har\s+mahine\s+fixed\s+\d|"
        r"10\s*guna|salary\s+triple|lakh\s+bana\w+|hazaar\s+ko\s+\d*\s*lakh|"
        r"पक्का\s+मुनाफा|पैसा\s+डबल|गारंटी\w*|तय\s+\d*\s*गुना|"
        r"रोज\s+[\d०-९]+\s+\S+\s+मुनाफा|लाखों?\s+कमाएं|तीन\s*गुना|"
        r"तय\s+\d*\s*गुना|(\d+|तीन|दो|पांच)\s*गुना\s+"
        r"(होगा|होगी|होंगे|मुनाफा|रिटर्न|लाभ|करें|करेगा|बनाएं)|"
        r"प्रतिशत\s+मुनाफा|"
        r"\d+\s*लाख\s+(\S+\s+)?(कमाय|बनाए|बनाएं)|"
        r"सैलरी\s+तीन\s*गुना|लाख\s+बनाएं|हजार\s+को\s+\d*\s*लाख)",
        "It promises a specific result (guaranteed/doubled returns), which no "
        "legitimate educator can assure.",
    ),
    (
        "risk_downplay",
        "risk_denial",
        r"(\bno[\s-]?risk\b|zero[\s-]?\s*risk|without\s+risk|100\s?%\s*safe|fully\s+safe|"
        r"no[\s-]?loss|zero\s+loss|loss\s+impossible|safe\s+and\s+sure|"
        r"koi\s+risk\s+nahi|risk\s+nahi|bina\s+risk|risk[-\s]?free|"
        r"\bsafe\s+(investment|trade|option|tip)|"
        r"पूरी\s+तरह\s+सुरक्षित|सौ\s+प्रतिशत\s+सुरक्षित|बिल्कुल\s+सुरक्षित|"
        r"रिस्क\s+नहीं|जोखिम\s+नहीं|बिना\s+जोखिम|बिना\s+नुकसान|"
        r"न\s+कभी\s+नुकसान|नुकसान\s+असंभव)",
        "It describes the idea as risk-free or safe, hiding that all market "
        "products carry risk.",
    ),
    (
        "fake_authority",
        "authority",
        r"(ex-?sebi|ex[\s-]?insider|sebi\s+insider|insider\s+tip|"
        r"secret\s+(source|trick|strategy)|institutional\s+(secret|desk|trader)|"
        r"bank\s+(manager|official|leak)|insurance\s+officer|fund\s+manager\s+friend|"
        r"rbi[\s-]?approved|i\s+am\s+sebi[\s-]?registered|main\s+sebi[\s-]?registered|"
        r"insiders?\s+(confirm|said|tip)|"
        r"ex[\s-]?broker|inside\s+(a\s+)?brokerage|desk\s+trader|leak\w*|"
        r"leaked\s+(circular|notice)|"
        r"9500\s*crore|confidential\s+(info|information|source)|operator\s+game|"
        r"पूर्व\s+अधिकारी|गोपनीय|अंदरूनी|लीक|बैंक\s+(अधिकारी|मैनेजर)|"
        r"बीमा\s+अधिकारी|पूर्व\s+ब्रोकर|मैं\s+सेबी)",
        "It leans on an unverifiable insider/secret source instead of a "
        "checkable fact.",
    ),
    (
        "paid_service_cta",
        "product_pitch",
        r"(join\s+(our|my|the|us)\s+(group|channel|telegram|whatsapp|premium|vip)|"
        r"join\s+now|join\s+us\b|join\s+kar\w+|group\s+join|link\s+in\s+bio|"
        r"bio\s+me\w*\s+link|bio\s+ke\s+link|mere\s+link\s+se|dm\s+(me|now|for)|"
        r"dm\s+karo|message\s+me\b|message\s+karo|"
        r"download\s+(the\s+)?app|app\s+\w*\s*download|"
        r"premium\s+(group|call|tip|channel|members?)|paid\s+(group|service|call|community|channel)|"
        r"my\s+referral|referral\s+se|vip\s+group|whatsapp\s+channel|"
        r"telegram\s+pe|whatsapp\s+pe|"
        r"subscription|course\s+(buy|join|enroll)|enrollment\s+open|enroll\s+now|"
        r"enroll\s+karo|मैसेज\s+करें|"
        r"ग्रुप\s+से\s+जुड़ें|जॉइन\s+करें|जुड़ें|"
        r"प्रीमियम\s+(टेलीग्राम\s+)?(ग्रुप|चैनल|सेवा|कम्युनिटी|बैच|कोर्स)|"
        r"पेड|वीआईपी|"
        r"लिंक\s+से|ऐप\s+डाउनलोड|रेफरल|कम्युनिटी|बायो|खरीदें|दाखिला|सदस्यता)",
        "It directs viewers toward a group, app, or paid service. "
        "That is a classic promotion signal.",
    ),
    (
        "urgency_pressure",
        "urgency",
        r"(act\s+fast|hurry|last\s+chance|limited\s+(seats|offer|slots|time)|"
        r"only\s+\d+\s+(spots|seats|left|entries)|seats?\s+(left|are\s+filling)|"
        r"filling\s+(fast|up)|offer\s+ends|today\s+only|save\s+it\s+now|"
        r"batch\s+closes?|closes?\s+tonight|\bmidnight\b|\btonight\b|"
        r"before\s+it('s| is)\s+too\s+late|miss\s+(this|the)\s+chance|"
        r"jaldi\s+kar|turant|aaj\s+hi|aaj\s+raat|aakhri\s+mauka|seem?it\s+samay|"
        r"sirf\s+\d+\s+(seats?|entries)|seats?\s+(bachi|bhar)|offer\s+\S*\s*khatm|"
        r"raat\s+\d+\s*baje|"
        r"जल्दी\s+करें|तुरंत|आखिरी\s+मौका|सीटें?|सिर्फ\s+\d+|ऑफर|आज\s+ही|आज\s+रात|"
        r"आधी\s+रात|सीमित|बंद\s+हो|खत्म\s+हो)",
        "It pressures quick action with urgency/scarcity instead of explaining "
        "the concept.",
    ),
    (
        "social_proof",
        "testimonial",
        r"(my\s+student|my\s+follower|client\s+earned|made\s+(lakhs?|crores?)|"
        r"earned\s+(lakhs?|crores?)|saved\s+\d+\s*lakh|"
        r"clients?\s+post\w*\s+earnings?|thanked\s+me|thank\s*you\s+bola|"
        r"made\s+lakhs?|earned\s+lakhs?|"
        r"profit\s+screenshots?|paisa\s+kamaya|lakhpati|crorepati|"
        r"\d+\s*lakh\s*(profit|kamaye|earned)|testimon\w+|review\s+dekh|"
        r"my\s+(\w+\s+)?(student|follower|client)s?[^.]{0,60}(lakh|profit|earn|made|saved|thank|clear)|"
        r"mere\s+(\w+\s+)?(student|follower|client)s?[^.]{0,60}(lakh|profit|kamay|kama|crore|bach|clear)|"
        r"छात्र|फॉलोअर|ग्राहक|लाखों?\s+कमाए?|स्क्रीनशॉट|करोड़पति|धन्यवाद)",
        "It uses a testimonial or profit story as proof instead of evidence "
        "you can verify.",
    ),
]

# Precision guards: skip a flag when the sentence carries an explicit
# debunking, negating, or technical-tax context. Each guard exists because
# a hand-reviewed education item misfired without it (see ids in comments).
_GUARDS: dict[str, list[str]] = {
    # edu-0015: "no loss set-off" is income-tax vocabulary, not a promise.
    "risk_downplay": [r"set[\s-]?off"],
    # edu-0009/edu-0040: warning readers that screenshots prove nothing.
    "social_proof": [
        r"prov\w+\s+nothing",
        r"can\s+be\s+faked",
        r"screenshot\w*\s+.*\bfake\b",
        r"\bfake\b\w*\s+screenshot",
        r"prove\s+n\w+\s+hota",
        r"fake\s+bhi",
        r"don'?t\s+trust",
        r"नकली",
        r"साबित\s+नहीं",
        r"कुछ\s+साबित",
    ],
    # edu-0022: "guarantee nahi milti" denies a guarantee; edu-0002
    # ("does not guarantee future results") must never fire.
    # edu-0069/0079/0089: condemning assured-profit promises (violating the
    # code, tod raha hai) is education about the rule, not a promise.
    "unrealistic_returns": [
        r"(does\s+not|do\s+not|never|no)\s+guarantee",
        r"guarantee\s+(nahi|nahin)",
        r"गारंटी\s+नहीं",
        r"violat\w*",
        r"prohibited",
        r"illegal",
        r"\bbanned\b",
        r"आचार\s+संहिता",
        r"तोड़\s+रहा",
        r"tod\s+raha",
    ],
    # edu-0084: condemning paid promotion is not a sales CTA.
    "paid_service_cta": [r"प्रतिबंधित", r"prohibited", r"\bbanned\b"],
    # edu-0023: "turant zarurat na ho" (money you do not need urgently).
    "urgency_pressure": [r"तुरंत\s+जरूरत\s+न"],
}

_DISCLOSURE_RE = re.compile(
    r"(mutual\s+fund.*subject\s+to\s+market\s+risk|market\s+risk|"
    r"risk\s+disclosure|do\s+your\s+own\s+research|dyor|"
    r"not\s+(financial|investment)\s+advice|educational\s+purpose|"
    r"consult\s+(a\s+)?(sebi[-\s]?registered|registered)\s+(advisor|adviser|"
    r"investment\s+advis(er|or)|research\s+analyst)|"
    r"sebi\s+registered|mutual\s+fund\s+sahi\s+hai|nivesh.*jokhim|"
    r"read\s+all\s+scheme\s+related\s+documents\s+carefully|"
    r"sips?\s+are\s+subject|past\s+performance)",
    re.IGNORECASE,
)

_FLAG_WEIGHTS = {
    "unrealistic_returns": 3,
    "risk_downplay": 2,
    "fake_authority": 2,
    "paid_service_cta": 2,
    "urgency_pressure": 1,
    "social_proof": 1,
    "missing_disclosure": 1,
}

_FLAG_LABELS = {
    "unrealistic_returns": "Guaranteed / unrealistic returns",
    "risk_downplay": '"No risk" / "safe" language',
    "fake_authority": "Fake / unverifiable authority",
    "paid_service_cta": "Call to join group / app / paid service",
    "urgency_pressure": "Urgency or scarcity pressure",
    "social_proof": "Testimonial used as evidence",
    "missing_disclosure": "Missing risk disclosure",
}

OFFICIAL_SOURCES = {
    # Verified official pages (checked Oct 1, 2026). Never link a page
    # we have not opened; fall back to the SEBI homepage is banned here.
    "ad_code_circular": (
        "https://www.sebi.gov.in/legal/circulars/apr-2023/"
        "advertisement-code-for-investment-advisers-ia-and-"
        "research-analysts-ra-_69798.html"
    ),
    "finfluencer_consultation": (
        "https://www.sebi.gov.in/reports-and-statistics/reports/aug-2023/"
        "consultation-paper-on-association-of-sebi-registered-"
        "intermediaries-regulated-entities-with-unregistered-entities-"
        "including-finfluencers-_75932.html"
    ),
    "ia_list": (
        "https://www.sebi.gov.in/sebiweb/other/OtherAction.do"
        "?doRecognisedFpi=yes&intmId=13"
    ),
    "intermediary_hub": (
        "https://www.sebi.gov.in/sebiweb/other/OtherAction.do?doRecognised=yes"
    ),
    "investor_site": "https://investor.sebi.gov.in/",
    "scores": "https://scores.sebi.gov.in/",
}

# Each rubric flag cites the source document(s) behind it. Only documents
# listed in the module docstring above may appear here.
FLAG_SOURCES: dict[str, list[str]] = {
    "unrealistic_returns": ["S1", "S2"],
    "risk_downplay": ["S1", "S3"],
    "fake_authority": ["S1", "S2"],
    "paid_service_cta": ["S1", "S2"],
    "urgency_pressure": ["S1", "S3"],
    "social_proof": ["S3"],
    "missing_disclosure": ["S1", "S3"],
}

# ---------------------------------------------------------------- helpers


def split_sentences(text: str) -> list[str]:
    """Naive sentence splitter incl. Hindi danda. Good enough for Day-1."""
    parts = re.split(r"(?<=[.!?\u0964\n])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def has_disclosure(text: str) -> bool:
    return bool(_DISCLOSURE_RE.search(text))


def analyze_text(text: str) -> dict:
    """Run the rubric over raw text. Returns the API response dict."""
    clean = text.strip()
    sentences = split_sentences(clean)
    disclosure_present = has_disclosure(clean)

    claims: list[dict] = []
    flags_hit: set[str] = set()

    for sent in sentences:
        for flag, claim_type, pattern, reason in _PATTERNS:
            if re.search(pattern, sent, re.IGNORECASE):
                if any(re.search(g, sent, re.IGNORECASE) for g in _GUARDS.get(flag, [])):
                    continue
                quote = sent if len(sent) <= 280 else sent[:277] + "..."
                # Verbatim validation: quote must occur in source.
                anchor = quote[:60]
                if anchor not in clean:
                    continue
                claims.append(
                    {
                        "quote": quote,
                        "claim_type": claim_type,
                        "flags": [flag],
                        "reason": reason,
                    }
                )
                flags_hit.add(flag)

    risky = bool(claims)
    if risky and not disclosure_present:
        flags_hit.add("missing_disclosure")

    score = sum(_FLAG_WEIGHTS[f] for f in flags_hit)

    if score == 0:
        classification, caution = "education", "low"
    elif score >= 5:
        classification, caution = "promotion", "high"
    elif score == 1 and flags_hit == {"missing_disclosure"}:
        classification, caution = "education", "low"
        # Surface the nudge as a claim-like note? No — keep claims verbatim-only.
        # The verification panel carries the disclosure message instead.
    else:
        classification, caution = "mixed", "medium"

    summary = _summarize(classification, flags_hit, len(claims), disclosure_present)

    verification = [
        {
            "label": "SEBI registration",
            "status": "cannot_verify",
            "url": OFFICIAL_SOURCES["ia_list"],
            "note": "We cannot check advisor registration from text alone. "
            "Search the name on SEBI's official Investment Adviser list; "
            "other intermediary types are listed on SEBI's Recognised "
            "Intermediaries hub.",
        },
        {
            "label": "Risk disclosure",
            "status": "present" if disclosure_present else "missing",
            "url": OFFICIAL_SOURCES["investor_site"],
            "note": "A risk disclaimer was found."
            if disclosure_present
            else "No risk disclaimer found. Registered content must follow "
            "SEBI's advertisement code (CIR/2023/51); mutual-fund content "
            "must carry the standard market-risk warning.",
        },
        {
            "label": "Official circular / notice",
            "status": "cannot_verify",
            "url": OFFICIAL_SOURCES["ad_code_circular"],
            "note": "If the content cites a SEBI circular, verify it on "
            "SEBI's official site. Start with the IA/RA advertisement code "
            "circular (CIR/2023/51, Apr 5 2023); we cannot confirm any "
            "citation from text alone.",
        },
    ]

    return {
        "classification": classification,
        "caution_level": caution,
        "caution_score": score,
        "summary": summary,
        "claims": claims,
        "flags": sorted(flags_hit),
        "flag_labels": [_FLAG_LABELS[f] for f in sorted(flags_hit)],
        "verification": verification,
        "disclaimer": DISCLAIMER,
        "rubric_version": RUBRIC_VERSION,
    }


def _summarize(
    classification: str, flags: set[str], n_claims: int, disclosure: bool
) -> str:
    if classification == "education":
        base = (
            "This looks like straightforward financial education. "
            "No promotional patterns were detected"
        )
        base += " and a risk disclaimer is present." if disclosure else "."
        return base
    if classification == "promotion":
        top = ", ".join(_FLAG_LABELS[f] for f in sorted(flags)[:3])
        return (
            f"This content promotes rather than teaches. Detected {n_claims} "
            f"flagged claim(s) including: {top}. Treat return promises and "
            "paid-group invites with skepticism."
        )
    if not flags:
        return "No clear promotional pattern, but the wording is ambiguous. Read carefully."
    top = ", ".join(_FLAG_LABELS[f] for f in sorted(flags)[:3])
    return (
        f"This content mixes explanation with promotion. Flagged {n_claims} "
        f"claim(s): {top}. Verify names and notices on official SEBI pages."
    )
