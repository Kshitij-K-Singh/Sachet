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

Caution score = sum of pattern weights still ships on the response for
  continuity, but it decides nothing. It is raw signal mass, not a grade.

Classification (v1.5):
  The decision is made by counting INDEPENDENT PERSUASION CATEGORIES, not by
  summing pattern weights. Thresholds are measured, not guessed: across the
  254-item corpus, education is 95/95 at zero categories, promotion is 85/88
  at two or more, and mixed is 59/71 at exactly one.

  >= 2 categories       -> promotion   (a pattern, not a bad sentence)
  == 1 category         -> mixed      (label: educational + a red flag)
  == 0 categories       -> education
  question asked        -> question               (never a verdict)
  no finance subject    -> out_of_scope           (never a verdict)
  too short to judge    -> insufficient_context   (never a verdict)

Scope gate (out_of_scope):
  Promotional patterns can appear in ANY text, so a flag alone does not
  prove financial content. When the rubric fires nothing AND the text
  contains no finance-domain vocabulary, the tool is being fed content
  it was not built for (pizza, football, weather). It says so instead of
  returning a confident "education" verdict that nobody asked for.
  Any single promo flag OR any finance term keeps the normal verdict.

Question gate (question):
  A user asking a question is not content to grade either. "Will 100 rupees
  double in 2 years?" scored 0 and returned "straightforward financial
  education" -- a confident verdict about the user's own doubt. v1.4 returns
  `question` with caution_level `not_applicable` and a guidance[] list that
  answers with arithmetic and regulation, never a return forecast
  (predicting returns would be the advice DISCLAIMER disclaims). Fires only
  when EVERY clause is interrogative, finance vocabulary is present, and no
  substantive promo flag fired -- so a question-shaped caption ("Paisa kaise
  lagaye? SIP start karo...") and a question about a pitch ("should I join
  their guaranteed 10x group?") both stay on the rubric path. Validated
  against all 254 corpus items -> 0 reclassified.

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

RUBRIC_VERSION = "rubric-v1.5"

DISCLAIMER = "This is an awareness tool, not investment advice."
_DISCLAIMER_HI = "यह जागरूकता उपकरण है, निवेश सलाह नहीं।"

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
        # Noun-first phrasing ("a return of 60%") reverses the word order the
        # pattern above assumes. The horizon token is what distinguishes a
        # promise from edu-0003's "12% annualised returns over very long
        # periods", so a bare number still must not fire.
        r"(?:returns?|profit|gain|yield|payout)\s+(?:of|is|:)?\s*\d+\s?(?:%|percent)|"
        r"\d+\s?(?:%|percent)\s*(?:return|profit|gain|yield)\s*"
        r"(?:in|within|over|every|per|each)\s+"
        r"(?:the\s+)?(?:next\s+)?\d+\s*(?:day|week|month|quarter|yr|year)|"
        # Spelled-out horizon: "over the next three months".
        r"(?:returns?|profit|gain|yield)\s+(?:of\s+)?\d+\s?(?:%|percent)"
        r"[^.]{0,30}?(?:next|coming|following)\s+"
        r"(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|twelve|couple\s+of)"
        r"[- ]*(?:day|week|month|quarter)|"
        # Hinglish/Devanagari put the horizon BEFORE the percentage
        # ("3 mahine me 60 percent", "तीन महीने में 60 प्रतिशत"), the reverse
        # of the English order above. Corpus-checked: no education item hits.
        r"\d+\s*(?:mahine|mahina|mahin|month|week|saal|year|din|day)[a-z]*\s*"
        r"(?:me|in|में)\s*\d+\s*(?:%|percent)|"
        r"(?:%|प्रतिशत)\s*(?:का\s*)?(?:रिटर्न|मुनाफा|लाभ)|"
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
        r"my\s+(students?|followers?|clients?|members?|family)\s+(made|earned|profited)|"
        r"\d[\d,]*\s*(?:lakh|crore|member|members|log|investor|investors)\b|"
        r"mere\s+\d[\d,]*\s*(?:log|member|student)|"
        r"verified\s+by\s+\d|sabke\s+account\s+me|"
        r"(?:mere|hamare|my|our)\s+\d+\s*(?:students?|members?|followers?|log)|"
        r"ex[\s-]?broker|inside\s+(a\s+)?brokerage|desk\s+trader|leak\w*|"
        r"leaked\s+(circular|notice)|"
        r"9500\s*crore|confidential\s+(info|information|source)|operator\s+game|"
        # Real markers SEBI names in actual orders and advisories. These were
        # genuine coverage gaps: every one below appears in enforcement
        # actions (false NISM certification, "institutional" account claims,
        # guaranteed IPO allotment, accuracy-as-proof, "no risk of loss").
        r"nism\s*(certified|certification)|sebi\s*(approved|registered|licensed)|"
        r"institutional\s*(desk\s*)?(account|access|allocation|trading)|"
        r"ex-?banker|ex[\s-]?banker|desk\s+trader|proprietary\s+desk|"
        r"guaranteed\s+allotment|allotment\s+guaranteed|"
        r"(\d{2,3})\s?%\s*(accuracy|accurate)|accuracy\s+(of\s+)?\d{2,3}\s?%|"
        r"unbeatable\s+accuracy|hit\s+rate|assured\s+profit|"
        r"risk\s*reward\s*1\s*:\s*\d|winning\s+accuracy|"
        r"task\s+based\s+(earning|trading|job)|recharge\s+(karo|kar)\w*|"
        r"withdrawal\s+fee|unlocking\s+fee|unlock\s+(your\s+)?(money|amount)|"
        r"no\s+risk\s+of\s+loss|principal\s+(is\s+)?(guarantee|returned)|"
        r"daily\s+(payout|income|withdrawal)|"
        r"सीएससी|टीसीएस|एनआईएसएम\s*प्रमाणित|संस्थागत\s*(खाता|डेस्क)|"
        r"रिफंड\s+कर|निकासी\s+शुल्क|वापस\s+कर\s+ने|"
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
        # Real recruitment phrasings from SEBI advisories: unsolicited
        # WhatsApp/Telegram invites, VIP and "discounted trading" groups.
        r"join\s+(?:my|our|this)\s+\S{0,12}\s*(group|channel|community|club)|"
        r"whatsapp\s+group|telegram\s+(group|channel)|discord\s+(link|server)|"
        r"\bdm\s+(?:me|me\s+to|for)\b|\bmessage\s+me\b|number\s+in\s+bio|"
        r"registration\s+fee|join\s+fee|entry\s+fee|membership\s+fee|"
        r"seat\s+(?:left|limited|full)|limited\s+seats|last\s+\d+\s+seats|"
        r"offer\s+(?:ends|expire|closes)|closing\s+tonight|"
        r"jaldi\s+kar\w*|abhi\s+(?:se|hi)\s+jud\w*|band\s+ho\s*(?:rahi|jayeg)|"
        r"slot\s+bhar|seats?\s+(?:fill|bhar)\w*|"
        r"सीट\s*(खत्म|भर|बंद)|जल्दी\s+कर|अभी\s+जुड़|लिंक\s+बायो|"
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
        # Act-now purchase directive ("buy ... today"). Distinct from
        # "today only" above: the instruction targets the trade itself,
        # not an offer deadline. Corpus-checked: fires on no education item.
        r"\b(?:buy|purchase|invest|start|apply|open)\w*\b[^.]{0,40}"
        r"\b(?:today|right\s+now|aaj\s+hi|abhi)\b|"
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

# Hindi claim reasons, keyed by the same stable flag codes used in _PATTERNS.
# Quotes stay verbatim in the source language; only this explanation is localized.
_REASONS_HI = {
    "unrealistic_returns": (
        "यह कोई खास नतीजा देने का वादा करता है (गारंटीड/दोगुना रिटर्न), "
        "जिसकी कोई असली शिक्षक गारंटी नहीं दे सकता।"
    ),
    "risk_downplay": (
        "यह विचार को जोखिम-मुक्त या सुरक्षित बताता है, जबकि बाज़ार के सभी "
        "उत्पादों में जोखिम होता है।"
    ),
    "fake_authority": (
        "यह जाँच योग्य तथ्य के बजाय किसी अप्रमाणित अंदरूनी/गुप्त स्रोत का "
        "सहारा लेता है।"
    ),
    "paid_service_cta": (
        "यह दर्शकों को किसी ग्रुप, ऐप या सशुल्क सेवा की ओर ले जाता है। यह "
        "प्रचार का जाना-पहचाना संकेत है।"
    ),
    "urgency_pressure": (
        "यह अवधारणा समझाने के बजाय जल्दबाज़ी/कमी के दबाव से तुरंत कार्रवाई "
        "करवाता है।"
    ),
    "social_proof": (
        "यह जाँच योग्य प्रमाण के बजाय किसी प्रशंसा-पत्र या मुनाफे की कहानी "
        "को प्रमाण बनाता है।"
    ),
}


def _reason_text(ui_language: str, flag: str) -> str:
    """Localized claim reason for a stable flag code.

    English is read back out of _PATTERNS so the tested wording cannot drift
    from the rubric definition; Hindi falls back to English for unknown codes.
    """
    if _normalize_ui_language(ui_language) == "hi":
        for candidate, _, _, english in _PATTERNS:
            if candidate == flag:
                return _REASONS_HI.get(flag, english)
        return ""
    for candidate, _, _, english in _PATTERNS:
        if candidate == flag:
            return english
    return ""

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

# Domain vocabulary for the scope gate. Deliberately broad and bilingual:
# a false positive here only means we run the normal rubric on an off-topic
# text (the safe failure), while a false negative would hide a real scam
# behind an "out of scope" banner. So: err toward matching.
_FINANCE_RE = re.compile(
    r"(stock|share|market|mutual\s*fund|\bsip\b|etf|index\s*fund|bond|debenture|"
    r"equit\w+|portfolio|invest\w*|nivesh|trading|trade\b|demat|broker\w*|"
    r"ipo|fund\s+house|asset\s+management|nav\b|emi\b|loan|insurance|insur\w*|"
    r"retirement|pension|provident\s+fund|\bepf\b|tax\b|income\s+tax|gst\b|"
    # edu-0048/0052/0060/0093: credit, commissions, expense ratios and
    # finfluencer rules are finance content too. Without these the gate
    # mislabelled 5 real education items as out_of_scope.
    r"credit\s*score|penal\w+|commission|expense\s+ratio|finfluencer|"
    r"rebalanc\w+|direct\s+plan|regular\s+plan|payout|demat\b|"
    r"वितरक|कमीशन|खर्च\s+अनुपात|रेगुलर|डायरेक्ट|प्लान|डिस्काउंट|"
    r"कम\s+रहता|लॉक-इन|अंश|म्यूचुअल\s+फंड|अनुपात|"
    r"inflation|interest\s+rate|repo\s+rate|rbi|sebi|nse\b|bse\b|sensex|nifty|"
    # Batch-3 vocabulary gap: real finance terms the gate was missing, so
    # items about them were wrongly routed to out_of_scope.
    r"small\s?cap|large\s?cap|mid\s?cap|market\s+cap|market\s+capital|"
    r"\bswp\b|systematic\s+withdrawal|withdrawal\s+plan|"
    r"behaviou?r\w*|bias\b|biases\b|herd\s+mentality|loss\s+aversion|"
    r"recency\s+bias|sequence\s+of\s+returns|tracking\s+error|"
    r"duration\b|index\s+tracking|arbitrage|leverage|margin\s+call|"
    r"\bdiv\b|\bdividend\b|payout\s+ratio|expense\s+ratio|load\b|"
    r"gratuity|esop\b|\bkfs\b|provident\s+fund|retirement\s+corridor|"
    r"\bgratu\b|छाप\b|व्यवहार|पक्षपात|अभिमान|"
    r"gold\s+etf|etf\b|reit\b|\bdicgc\b|deposit\s+insurance|"
    r"\bdemat\b|स्वास्थ्य\s+बीमा|जीवन\s+बीमा|बीमा|"
    r"\bcdsl\b|\bcssc\b|\bnps\b|\bepfo\b|\bpsp\b|"
    r"\bnomination\b|nominee\b|\bkyc\b|upi\b|qr\s+code|sim\s+swap|"
    r"टैक्स|कर\s*छूट|धोखाधड़ी|निवेशक|बचत|"
    r"behaviour\w*|cognitive\s+bias|fomo\b|anchoring\b|"
    r"bank\w*|nbhb|nbfc|credit\s*card|debit\s*card|upi\b|neft|rtgs|"
    r"profit|loss|earn\w*|income|salary|revenue|turnover|compound\w*|interest\b|"
    r"dividend|yield|return\w*|fund\b|scheme\b|"
    r"crypto|bitcoin|ethereum|blockchain|nft\b|forex|commodit\w+|gold\s+price|"
    r"silver\s+price|real\s*estate|property\s+investment|"
    r"pais[ae]\b|paise\b|rupay|rupee|lakh|crore|lakhs|crores|salary|paisa|"
    r"बाज़ार|बाजार|शेयर|शेयरी|म्यूचुअल|फंड|निवेश|निवेशक|पैसा|पैसे|रुपया|रुपये|"
    r"लाख|करोड़|करोड|मुनाफा|नुकसान|लाभ|रिटर्न|आय|वेतन|ब्याज|बैंक|बैंकिंग|"
    r"मासिक|emi|ईएमआई|बीमा|सेवा|खाता|ऋण|कर|टैक्स|रिटायर|पेंशन|"
    r"सेबी|आरबीआई|शेयर बाजार|सोना|चांदी)",
    re.IGNORECASE,
)

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

# Display strings may be localized for the UI language, but rubric codes never
# are. Flags, claim types, categories, statuses, and classifications stay stable
# English identifiers; only the human-readable labels/reasons/notes change.
_FLAG_LABELS_HI = {
    "unrealistic_returns": "गारंटीड / अवास्तविक रिटर्न",
    "risk_downplay": '"कोई जोखिम नहीं" / "सुरक्षित" भाषा',
    "fake_authority": "नकली / अप्रमाणित अधिकार",
    "paid_service_cta": "ग्रुप / ऐप / सशुल्क सेवा में जुड़ने की बात",
    "urgency_pressure": "जल्दबाज़ी या कमी का दबाव",
    "social_proof": "प्रमाण के रूप में प्रशंसा-पत्र",
    "missing_disclosure": "जोखिम प्रकटीकरण नहीं",
}


def _normalize_ui_language(ui_language: str | None) -> str:
    """UI display language. Unknown values fall back to English."""
    return ui_language if ui_language in ("en", "hi") else "en"


def _flag_label(ui_language: str, flag: str) -> str:
    if _normalize_ui_language(ui_language) == "hi":
        return _FLAG_LABELS_HI.get(flag, _FLAG_LABELS[flag])
    return _FLAG_LABELS[flag]

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


# ---------------------------------------------------------------- questions

# A person asking a question is not content we can grade. This is the same
# failure mode as the out_of_scope gate below: without it, "if I invest 100
# rupees will it double in 2 years" scores 0 and returns a confident
# "straightforward financial education" verdict about the user's own doubt.
#
# Validated Oct 3 against all 254 dataset items -> 0 matches, so the rubric
# path is untouched. Tightened after bare `which is` matched two mixed.jsonl
# items via the relative clause "which is why"; `which` therefore only pairs
# with a finance noun, never with `is` on its own.
_QUESTION_RE = re.compile(
    r"\?\s*\z"
    r"|\b(?:will|can|could|should|would|shall)\s+"
    r"(?:i|we|you|it|they|he|she|this|that|these|those|"
    r"my|our|your|his|her|their|its)\b"
    r"|\bhow\s+(?:do|can|could|should|would|to|much|many)\b"
    r"|\bwhat\s+(?:is|are|should|would|happens)\b"
    r"|\bwhich\s+(?:mutual|fund|policy|bank|one\s+is\s+better)\b"
    r"|\b(?:is|are|does|do|did|was|were|has|have)\s+"
    r"(?:it|this|that|investing|investment)\b"
    r"|\bkya\b|\bkaise\b|\bkitna\b|\bkahan\b|\bkyu\b|\bkitne\b"
    # Devanagari wh-words are deliberately NOT listed here. They are matched
    # positionally in _clause_is_question instead, because Devanagari has no
    # ASCII word boundary (क्यों is a prefix of क्योंकि = "because") and Hindi
    # places the wh-word at the end, where Latin-script rules do not apply.
    # Matching them positionally also stops "देखें कि बेंचमार्क क्या है"
    # ("check *what* the benchmark is") being read as a question.
    r"$",
    re.IGNORECASE,
)

# Devanagari interrogative, matched only near the head or tail of a clause.
# Hindi puts the wh-word at either end ("क्या ... है" / "... है क्या"), but a
# wh-word in the MIDDLE is a noun clause inside a declarative sentence
# ("देखें कि बेंचमार्क क्या है" = "check what the benchmark is"). So head-or-
# tail is the discriminator, not mere presence.
_HI_QUESTION_RE = re.compile(r"क्या|कैसे|कितना|कितने|कहाँ|क्यों(?!कि)")
_HI_TAIL_WINDOW = 30
_HI_HEAD_WINDOW = 10

# Substantive promo flags mean the text really is a pitch someone is being
# handed ("should I join their guaranteed 10x group?"). The user there is
# asking us to grade the pitch, so those stay on the rubric path. Only text
# the rubric cannot grade at all becomes a question. missing_disclosure is
# deliberately excluded: it is derived, not authored, and would swallow every
# risk-free-sounding question.
_PROMO_SUBSTANTIVE = {
    "unrealistic_returns",
    "risk_downplay",
    "fake_authority",
    "paid_service_cta",
}

# Ordered, first match wins.
_QUESTION_INTENTS: list[tuple[str, str]] = [
    ("returns", r"double|doubl\w+|2x|10x|multipl\w+|tripl\w+|return|profit|"
                r"gain|yield|money|बढ़|मुनाफा|रिटर्न|पैसा|डबल"),
    ("safety", r"safe|safety|risk|scam|fraud|legit|real|padhai|पगली|"
               r"ठग|सुरक्षित|रिस्क|जोखिम"),
    ("comparison", r"better|best|vs\b|versus|compare|or\b|which|अच्छा|बेहतर|सबसे"),
    ("howto", r"how\s+(?:do|can|to|start|begin)|start|begin|कैसे|कब|कैसे\s+शुरू"),
]

# Required annualised return for a given horizon. Pure arithmetic, used to
# show the size of what a doubling promise implies -- not a forecast.
_HORIZON_YEARS = {
    "month": 1 / 12, "months": 1 / 12, "monthly": 1 / 12,
    "week": 1 / 52, "weeks": 1 / 52,
    "year": 1.0, "years": 1.0, "yr": 1.0, "yrs": 1.0,
    "saal": 1.0, "sal": 1.0, "साल": 1.0,
    "din": 1 / 365, "day": 1 / 365, "days": 1 / 365,
}
_NUM_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "a": 1, "an": 1,
    "दो": 2, "तीन": 3, "चार": 4, "पांच": 5, "पाँच": 5, "एक": 1,
}
_HORIZON_RE = re.compile(
    r"\b(\d{1,3}|one|two|three|four|five|six|seven|eight|nine|ten|a|an)\s*[- ]*"
    r"(month|months|monthly|week|weeks|year|years|yr|yrs|saal|sal|din|day|days|"
    r"महीना|महीने|साल|दिन)\b",
    re.IGNORECASE,
)


def _required_annual_pct(years: float) -> int:
    """Annualised return a doubling (or Nx) claim implies. Arithmetic only."""
    if years <= 0:
        return 0
    return round(((2 ** (1 / years)) - 1) * 100)


def _doubling_math(text: str) -> str | None:
    """If the question asks about doubling/multiples over a stated horizon,
    return the implied annualised return. Used only as arithmetic context."""
    if not re.search(r"double|doubl\w+|2x|tripl\w+|10x|multipl\w+", text, re.IGNORECASE):
        return None
    m = _HORIZON_RE.search(text)
    if not m:
        return None
    raw_n = m.group(1).lower()
    n = int(raw_n) if raw_n.isdigit() else _NUM_WORDS.get(raw_n)
    if not n:
        return None
    unit = m.group(2).lower()
    years = _HORIZON_YEARS.get(unit)
    if not years:
        return None
    return str(_required_annual_pct(n * years))


# A question can be *about* a specific pitch rather than a general doubt.
# "Will it triple in 2 years?" is a user thinking out loud; "should I join
# THEIR GROUP for guaranteed 10x?" is someone asking us to grade a named
# commercial offer. The second is a grading request, so it must not be
# deflected into the question branch.
_COMMERCIAL_REF_RE = re.compile(
    r"\b(?:group|channel|telegram|whatsapp|discord|course|app|platform|"
    r"premium|vip|membership|subscription|mentor|guru|masterclass)\b"
    r"|\bjoin\b|\bsign\s+up\b|\bdm\s+me\b|\blink\s+in\s+bio\b"
    r"|ग्रुप|टेलीग्राम|व्हाट्सएप|कोर्स|ऐप",
    re.IGNORECASE,
)


def _is_question(text: str) -> bool:
    """True only when *every* clause is interrogative.

    Precision matters more than recall here. Captions and explainers are
    routinely phrased as a question ("Paisa kaise lagaye? Mutual fund SIP start
    karo, pehle documents padho"), and treating those as questions would
    defang the rubric on exactly the content it exists to grade. So a question
    followed by any trailing instruction stays on the rubric path.
    """
    # Guard only on "is there any interrogative signal at all". The
    # accept/reject decision is _clause_is_question, which applies the
    # head-or-tail rule for Devanagari. Guarding on _QUESTION_RE alone would
    # reject every Devanagari-only question, since those markers are
    # deliberately not in _QUESTION_RE.
    if not (_QUESTION_RE.search(text) or _HI_QUESTION_RE.search(text)):
        return False
    # Split *after* the terminator (lookbehind) so each clause keeps its "?"
    # or danda -- _QUESTION_RE relies on that terminator for bare questions.
    clauses = [c.strip() for c in re.split(r"(?<=[?!.।\u0964])|\n", text) if c.strip()]
    if not clauses:
        return False
    return all(_clause_is_question(c) for c in clauses)


def _clause_is_question(clause: str) -> bool:
    """One clause is interrogative if it matches the Latin rules, or carries a
    Devanagari wh-word at its head or its tail."""
    if _QUESTION_RE.search(clause):
        return True
    if _HI_QUESTION_RE.search(clause[-_HI_TAIL_WINDOW:]):
        return True
    return bool(_HI_QUESTION_RE.search(clause[:_HI_HEAD_WINDOW]))


def _question_intent(text: str) -> str:
    for intent, pattern in _QUESTION_INTENTS:
        if re.search(pattern, text, re.IGNORECASE):
            return intent
    return "general"


# --------------------------------------------------------- evidence model
#
# v1.5 replaces the weighted score ladder. The old design summed per-pattern
# weights and cut at fixed thresholds, which made the verdict a function of
# *which keywords happened to be written down*:
#
#   "will it double"    -> 0 points -> question   (double needs "money")
#   "will it triple"    -> 3 points + 1 derived  -> mixed
#   "will it quadruple" -> 0 points -> question   (not in the pattern list)
#
# One unmatched word was enough to cross a threshold, and the derived
# missing_disclosure flag doubled a single match for free. That is not
# classification, it is keyword coverage with a confidence attached.
#
# The replacement counts *independent persuasion categories* instead. A
# return promise is one signal. A return promise PLUS a call to action is a
# pattern -- that is what actually distinguishes selling from explaining.
# No single word can reach a threshold, so adding or dropping a keyword can
# no longer flip the verdict.

# claim_type -> persuasion category. Categories are the unit of evidence:
# several patterns may map to one category, so repetition of the same tactic
# cannot manufacture a stronger signal than one instance of it.
_PERSUASION_CATEGORY = {
    "return_promise": "return_promise",
    "risk_denial": "risk_denial",
    "authority": "authority_claim",
    "product_pitch": "commercial_cta",
    "urgency": "urgency",
    "testimonial": "social_proof",
}

PERSUASION_LABELS = {
    "return_promise": "Guaranteed or implausible return",
    "risk_denial": "Risk downplayed or denied",
    "authority_claim": "Unverifiable authority or insider claim",
    "commercial_cta": "Call to action for a paid service or product",
    "urgency": "Urgency or scarcity pressure",
    "social_proof": "Testimonial used as proof",
}

_PERSUASION_LABELS_HI = {
    "return_promise": "गारंटीड या अविश्वसनीय रिटर्न",
    "risk_denial": "जोखिम कम करके बताना या इनकार",
    "authority_claim": "अप्रमाणित अधिकार या अंदरूनी दावा",
    "commercial_cta": "सशुल्क सेवा या उत्पाद के लिए कार्रवाई की बात",
    "urgency": "जल्दबाज़ी या कमी का दबाव",
    "social_proof": "प्रमाण के रूप में प्रशंसा-पत्र",
}


def _persuasion_label(ui_language: str, category: str) -> str:
    if _normalize_ui_language(ui_language) == "hi":
        return _PERSUASION_LABELS_HI.get(category, PERSUASION_LABELS[category])
    return PERSUASION_LABELS[category]

# Positive evidence that content TEACHES. Required to call something
# "educational": the absence of persuasion signals is not evidence of
# education, it is absence of evidence. Without this, a 10-word neutral
# sentence was labelled educational and read as a clean bill of health.
_EDUCATION_RE = re.compile(
    # explicit framing
    r"for\s+educational\s+purposes?|educational\s+purposes?|not\s+investment\s+advice|"
    r"शैक्षणिक|सीखने\s+के\s+लिए|सिखाने\s+के\s+लिए|"
    # mechanism / explanation language
    r"\bmeans\s+that\b|\bmeans\b|\bbecause\b|\bso\s+that\b|\btherefore\b|"
    r"due\s+to\b|\bfor\s+example\b|\bin\s+simple\s+terms\b|\bhow\s+it\s+works\b|"
    r"\bconcept\b|\bmechanism\b|\bdefinition\b|\bworks\s+by\b|\bdepends\s+on\b|"
    r"इसका\s*मतलब|क्योंकि|उदाहरण|"
    # acknowledges trade-offs and risk -- the core of genuine education
    r"\brisk\w*\b|\brisks\b|\bmay\s+vary\b|\bnot\s+guaranteed\b|\btrade-?off\w*\b|"
    r"\bpros\s+and\s+cons\b|\bconsult\s+(a|an|your|with)\b|\bdue\s+diligence\b|"
    r"जोखिम|उतार-चढ़ाव|सलाह\s+लें|"
    # points at a checkable source
    r"\bsebi\b|\bas\s+per\b|\bsource\s*:|\bregulations?\b|\bprospectus\b|"
    r"\bdocuments?\b|\bscheme\s+related\b|\bread\s+all\b",
    re.IGNORECASE,
)

# Too short to carry a persuasion structure. A WhatsApp forward stripped of its
# author has no persuasion to find, and "nothing found" there must not be
# reported as "nothing wrong". 30 chars is roughly one short sentence: below
# it there is no room for both a claim and the context that would frame it.
# Deliberately far below the corpus minimum (89) so this gate never fires on
# ordinary captions -- it exists for fragments, not for short posts.
_MIN_CONTEXT_CHARS = 30

# Category count -> label. Promotion needs 2 independent categories; one
# category is a claim, not a pattern, and earns an abstention instead.
_PROMOTION_MIN_CATEGORIES = 2


def _education_markers(text: str) -> list[str]:
    out: list[str] = []
    for m in _EDUCATION_RE.finditer(text):
        q = m.group(0).strip()
        if q and q.lower() not in {o.lower() for o in out}:
            out.append(q)
        if len(out) >= 4:
            break
    return out


def _confidence(
    classification: str, categories: set[str], edu_markers: int, typed: bool
) -> float:
    """Auditable confidence in the LABEL.

    Deliberately not a model logit and not a vibe -- it is a documented
    function of the evidence actually observed, so a reviewer can recompute
    it and argue with the inputs rather than the number. Reported to 2dp.

    Abstentions report low confidence by construction: "unclear" means the
    evidence did not reach a threshold, and a low number here is the honest
    signal that the caller should not act on it.
    """
    n = len(categories)
    if classification in ("out_of_scope", "insufficient_context", "question"):
        # We are confident about the routing, not about a verdict we did not
        # give, so keep this low to avoid implying we ruled on the content.
        return 0.4 if typed else 0.5
    if classification == "promotion":
        # >=2 independent categories, saturating at 4. High and earned: this
        # is the only branch where we assert a pattern.
        return round(min(0.68 + 0.09 * (n - 2), 0.96), 2)
    if classification == "mixed":
        # Exactly one category. Deliberately low: a single tactic is a claim,
        # not a pattern, and we say so rather than dressing it up.
        return round(min(0.42 + 0.05 * edu_markers, 0.55), 2)
    # education: no persuasion found. Teaching markers, when present, raise
    # it; their absence caps it because we then only know a negative.
    return round(min(0.52 + 0.08 * min(edu_markers, 4), 0.9), 2)


def _verification_items(
    ui_language: str, classification: str, disclosure_present: bool
) -> list[dict]:
    """Fixed three-row official-source panel, localized for display.

    Labels, statuses, and URLs stay stable; only the human-readable label and
    note change. Risk-disclosure wording depends on routing and disclosure, so
    it mirrors the same branches used for the English response.
    """
    lang = _normalize_ui_language(ui_language)
    if lang == "hi":
        risk_note = (
            "लागू नहीं: यह टेक्स्ट वित्तीय सामग्री नहीं पहचाना गया।"
            if classification == "out_of_scope"
            else "लागू नहीं: सवाल प्रकाशित प्रचार नहीं है, इसलिए जोखिम "
            "प्रकटीकरण अपेक्षित नहीं है।"
            if classification == "question"
            else "जोखिम प्रकटीकरण मिला।"
            if disclosure_present
            else "कोई जोखिम प्रकटीकरण नहीं मिला। पंजीकृत सामग्री को SEBI के "
            "विज्ञापन कोड (CIR/2023/51) का पालन करना चाहिए; म्यूचुअल-फंड "
            "सामग्री में मानक बाज़ार-जोखिम चेतावनी होनी चाहिए।"
        )
        return [
            {
                "label": "SEBI पंजीकरण",
                "status": "cannot_verify",
                "url": OFFICIAL_SOURCES["ia_list"],
                "note": "टेक्स्ट से सलाहकार पंजीकरण जाँचा नहीं जा सकता। "
                "SEBI की आधिकारिक निवेश सलाहकार सूची में नाम खोजें; अन्य "
                "मध्यस्थ SEBI के मान्यता प्राप्त मध्यस्थ हब में सूचीबद्ध हैं।",
            },
            {
                "label": "जोखिम प्रकटीकरण",
                "status": "present" if disclosure_present else "missing",
                "url": OFFICIAL_SOURCES["investor_site"],
                "note": risk_note,
            },
            {
                "label": "आधिकारिक परिपत्रिका / सूचना",
                "status": "cannot_verify",
                "url": OFFICIAL_SOURCES["ad_code_circular"],
                "note": "अगर सामग्री में SEBI परिपत्रिका का हवाला है, तो उसे "
                "SEBI की आधिकारिक साइट पर जाँचें। IA/RA विज्ञापन कोड "
                "परिपत्रिका (CIR/2023/51, 5 अप्रैल 2023) से शुरुआत करें; "
                "टेक्स्ट से किसी उद्धरण की पुष्टि नहीं की जा सकती।",
            },
        ]

    risk_note = (
        "Not applicable: this text was not recognized as financial content."
        if classification == "out_of_scope"
        # A question is not required to carry a disclaimer -- the disclosure
        # rule binds publishers of promotion, not askers.
        else "Not applicable: a question is not published promotion, so "
        "no risk disclaimer is expected."
        if classification == "question"
        else "A risk disclaimer was found."
        if disclosure_present
        else "No risk disclaimer found. Registered content must follow "
        "SEBI's advertisement code (CIR/2023/51); mutual-fund content "
        "must carry the standard market-risk warning."
    )
    return [
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
            "note": risk_note,
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


def analyze_text(text: str, ui_language: str | None = "en") -> dict:
    """Run the rubric over raw text. Returns the API response dict.

    `ui_language` localizes display strings only ("en" or "hi"; anything else
    falls back to English). Rubric codes, quotes, and URLs never change.
    """
    lang = _normalize_ui_language(ui_language)
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
                        "reason": _reason_text(lang, flag),
                    }
                )
                flags_hit.add(flag)

    risky = bool(claims)
    if risky and not disclosure_present:
        flags_hit.add("missing_disclosure")

    # Independent persuasion categories present. This -- not the weighted
    # score -- is the unit of evidence the decision below counts.
    categories = {
        _PERSUASION_CATEGORY[c["claim_type"]]
        for c in claims
        if c["claim_type"] in _PERSUASION_CATEGORY
    }

    score = sum(_FLAG_WEIGHTS[f] for f in flags_hit)

    # Scope gate: a promo pattern is topic-agnostic, so only fall back to
    # out_of_scope when the rubric stayed silent AND the text reads as
    # non-financial. Any flag at all means the text is worth rating.
    #
    # A named commercial artefact also puts it in scope. "Can I pay to join
    # their telegram channel?" carries no finance vocabulary, but it is
    # precisely the question this tool exists to answer -- routing it to
    # out_of_scope would hide the target use case behind a keyword list.
    in_scope = (
        risky
        or bool(_FINANCE_RE.search(clean))
        or bool(_COMMERCIAL_REF_RE.search(clean))
    )

    # ---- Stage 1: speech act. Decided FIRST and authoritative.
    #
    # The person typing is not necessarily the person selling. "Will it
    # triple in 2 years?" is a user asking ABOUT a return claim; grading it
    # as though the user were making the promise is a category error. So the
    # utterance type is settled before any persuasion scoring, and a question
    # is never promoted/demoted on the strength of the words inside it.
    #
    # The one exception is a question used as a sales hook: "should I join
    # their group for guaranteed 10x returns?" is content with a question
    # mark on it. That is caught by requiring persuasive categories to exist
    # AND the text to carry a selling act (CTA / urgency / testimonial).
    asked = _is_question(clean)
    selling_categories = categories & {"commercial_cta", "urgency", "social_proof"}
    # A named commercial artefact only overrides the question branch when
    # there is something to grade. "Can I pay to join their telegram
    # channel?" asks about a service but asserts nothing, so it stays a
    # question; "should I join their group for guaranteed 10x?" carries a
    # return claim, so the user wants that graded.
    names_a_commercial_offer = bool(_COMMERCIAL_REF_RE.search(clean)) and bool(categories)
    is_question = (
        asked
        and in_scope
        and not selling_categories
        and not names_a_commercial_offer
    )

    # ---- Stage 2: sufficiency. Can this text carry a verdict at all?
    edu_markers = _education_markers(clean)

    if is_question:
        classification, label, scope = "question", "unclear", "in_scope"
    elif not in_scope:
        classification, label, scope = "out_of_scope", "unclear", "out_of_scope"
    elif len(clean) < _MIN_CONTEXT_CHARS and not categories:
        classification, label, scope = (
            "insufficient_context",
            "unclear",
            "insufficient_context",
        )
    # ---- Stage 3: label from independent categories, with abstention.
    #
    # Thresholds are measured, not guessed. Category-count distribution over
    # the 254-item corpus: education 95/95 at zero categories, promotion
    # 85/88 at two or more, mixed 59/71 at exactly one. So:
    #   >= 2 categories -> promotion   (a pattern, not a bad sentence)
    #   == 1 category   -> educational WITH a red flag = mixed
    #   == 0 categories -> educational, no red flags
    # A single keyword can only ever move one category in or out; it can no
    # longer cross a threshold, because crossing requires a different tactic.
    elif len(categories) >= _PROMOTION_MIN_CATEGORIES:
        classification, label, scope = "promotion", "promotion", "in_scope"
    elif categories:
        # One persuasion tactic in otherwise non-promotional text. Per the
        # brief this is the funnel case, so it stays "educational" with the
        # signal surfaced, rather than being promoted on thin evidence.
        classification, label, scope = "mixed", "educational", "in_scope"
    else:
        classification, label, scope = "education", "educational", "in_scope"

    caution = {
        "promotion": "high",
        "mixed": "medium",
        "education": "low",
    }.get(classification, "not_applicable")

    # caution_score stays on the response for continuity, but it is no longer
    # what decides anything. Kept as raw signal mass, not a grade.
    intent = _question_intent(clean) if is_question else None
    guidance = _question_guidance(intent, clean, lang) if is_question else []
    summary = _summarize(
        classification, flags_hit, len(claims), disclosure_present, intent, clean,
        categories, edu_markers, lang,
    )

    # Structured evidence, not a vague verdict. Each red flag carries the
    # verbatim span that produced it, so a user can see *why* and a reviewer
    # can audit the match without trusting a score.
    red_flags = [
        {
            "category": cat,
            "label": _persuasion_label(lang, cat),
            "quote": next(
                (c["quote"] for c in claims
                 if _PERSUASION_CATEGORY.get(c["claim_type"]) == cat),
                "",
            ),
            "note": next(
                (c["reason"] for c in claims
                 if _PERSUASION_CATEGORY.get(c["claim_type"]) == cat),
                "",
            ),
        }
        for cat in sorted(categories)
    ]
    what_to_verify = _what_to_verify(categories, disclosure_present, lang)

    verification = _verification_items(lang, classification, disclosure_present)

    return {
        "scope": scope,
        "label": label,
        "classification": classification,
        "caution_level": caution,
        "caution_score": score,
        "summary": summary,
        "claims": claims,
        "flags": sorted(flags_hit),
        "flag_labels": [_flag_label(lang, f) for f in sorted(flags_hit)],
        "persuasion_categories": sorted(categories),
        "red_flags": red_flags,
        "education_markers": edu_markers,
        "confidence": _confidence(classification, categories, len(edu_markers), is_question),
        "what_to_verify": what_to_verify,
        "guidance": guidance,
        "verification": verification,
        "disclaimer": DISCLAIMER if lang == "en" else _DISCLAIMER_HI,
        "rubric_version": RUBRIC_VERSION,
    }


def _what_to_verify(
    categories: set[str], disclosure_present: bool, ui_language: str = "en"
) -> list[str]:
    """Actionable checks, derived from which categories actually fired.

    Kept separate from the fixed verification panel: that one is always the
    same three rows, this one only lists what is relevant to *this* text.
    """
    if _normalize_ui_language(ui_language) == "hi":
        return _what_to_verify_hi(categories, disclosure_present)
    out: list[str] = []
    if "authority_claim" in categories:
        out.append(
            "Search the named person or firm on SEBI's recognised intermediary "
            f"list: {OFFICIAL_SOURCES['intermediary_hub']}"
        )
    if "commercial_cta" in categories:
        out.append(
            "Do not pay, or share OTPs or personal details, to get access to a "
            "group. Legitimate advisers are paid by the asset manager, not by "
            "you joining a chat."
        )
    if "return_promise" in categories:
        out.append(
            "Ask what annualised return is being promised, in writing. If the "
            "answer is a guaranteed figure, that is the finding on its own."
        )
    if "risk_denial" in categories:
        out.append(
            "Check what the product's own document says about risk. Registered "
            "products must carry a market-risk warning."
        )
    if "social_proof" in categories:
        out.append(
            "A profit screenshot is not evidence. Screenshots can be staged, "
            "and SEBI's advertisement code bars testimonials entirely."
        )
    if "urgency" in categories:
        out.append(
            "Artificial deadlines are a pressure tactic. A legitimate offer "
            "does not become invalid because you hesitated."
        )
    if not disclosure_present and (
        categories & {"return_promise", "risk_denial", "commercial_cta"}
    ):
        out.append(
            "No risk disclaimer was found. Registered promotion must follow "
            "SEBI's advertisement code (CIR/2023/51)."
        )
    if not out:
        out.append(
            "Nothing checkable was flagged here. That is not a clean bill of "
            f"health — verify names and figures on {OFFICIAL_SOURCES['investor_site']}"
        )
    return out


def _what_to_verify_hi(categories: set[str], disclosure_present: bool) -> list[str]:
    """Hindi version of the same category-driven checklist. URLs stay as-is."""
    out: list[str] = []
    if "authority_claim" in categories:
        out.append(
            "नाम वाले व्यक्ति या फर्म को SEBI की मान्यता प्राप्त मध्यस्थ "
            f"सूची में खोजें: {OFFICIAL_SOURCES['intermediary_hub']}"
        )
    if "commercial_cta" in categories:
        out.append(
            "किसी ग्रुप तक पहुँच के लिए भुगतान न करें, और OTP या व्यक्तिगत "
            "जानकारी साझा न करें। असली सलाहकारों को चैट में जुड़ने से नहीं, "
            "एसेट मैनेजर से भुगतान मिलता है।"
        )
    if "return_promise" in categories:
        out.append(
            "लिखित में पूछें कि कौन-सा वार्षिक रिटर्न देने का वादा है। अगर "
            "जवाब में गारंटीड आँकड़ा है, तो वही अपने आप में निष्कर्ष है।"
        )
    if "risk_denial" in categories:
        out.append(
            "उत्पाद के अपने दस्तावेज़ में जोखिम के बारे में क्या कहा गया है, "
            "वह देखें। पंजीकृत उत्पादों में बाज़ार-जोखिम चेतावनी होनी चाहिए।"
        )
    if "social_proof" in categories:
        out.append(
            "मुनाफे का स्क्रीनशॉट प्रमाण नहीं है। स्क्रीनशॉट बनाए जा सकते हैं, "
            "और SEBI के विज्ञापन कोड में प्रशंसा-पत्र पूरी तरह वर्जित हैं।"
        )
    if "urgency" in categories:
        out.append(
            "बनावटी समय-सीमा दबाव की चाल है। सही प्रस्ताव आपके हिचकिचाने से "
            "अवैध नहीं हो जाता।"
        )
    if not disclosure_present and (
        categories & {"return_promise", "risk_denial", "commercial_cta"}
    ):
        out.append(
            "कोई जोखिम प्रकटीकरण नहीं मिला। पंजीकृत प्रचार को SEBI के "
            "विज्ञापन कोड (CIR/2023/51) का पालन करना चाहिए।"
        )
    if not out:
        out.append(
            "यहाँ जाँच योग्य कुछ भी चिह्नित नहीं हुआ। यह स्वस्थ प्रमाणपत्र "
            "नहीं है — नाम और आँकड़े "
            f"{OFFICIAL_SOURCES['investor_site']} पर जाँचें।"
        )
    return out


def _question_guidance(
    intent: str | None, text: str, ui_language: str = "en"
) -> list[str]:
    """Answer a question honestly without forecasting returns.

    Everything here is arithmetic, regulation, or a place to verify. Nothing
    here tells the user what to do or what a product will return -- that is
    investment advice and this tool does not give it (see DISCLAIMER).
    """
    pct = _doubling_math(text)
    if _normalize_ui_language(ui_language) == "hi":
        return _question_guidance_hi(intent, pct)
    horizon = (
        f"Doubling over that horizon means about {pct}% every year, compounded. "
        "That is arithmetic, not a forecast: it is what any such promise has "
        "to deliver to be true."
        if pct
        else "Working out what return a claim implies is pure arithmetic, not "
        "a forecast: a doubling over n years needs about (2^(1/n) - 1) every "
        "year, compounded."
    )
    platform = (
        "Also check what you are actually buying. A broker, aggregator, or "
        "insurance marketplace is a shop window, not an investment: putting "
        "money into the platform does not make it grow."
    )
    common = [
        "No SEBI-regulated product can promise a fixed, guaranteed return. A "
        "guaranteed return claim is the single strongest scam signal there is.",
        f"Verify anything you are considering on SEBI's official site: "
        f"{OFFICIAL_SOURCES['investor_site']}",
    ]
    by_intent = {
        "returns": [
            horizon,
            platform,
            *common,
        ],
        "safety": [
            "A regulated product will always carry market risk. 'Safe' in a "
            "financial context usually means one of: a deposit insurance limit, "
            "a government-backed bond, or someone describing a loss as "
            "impossible. Ask which one they mean.",
            "Check the intermediary's name on SEBI's recognised list before "
            f"sharing any personal detail: {OFFICIAL_SOURCES['intermediary_hub']}",
            *common,
        ],
        "comparison": [
            "Comparing products usually turns on tax treatment, exit load, and "
            "risk, not on the headline number. Those three decide most cases "
            "more than the rate does.",
            "Read the scheme's own document on the AMC's site rather than a "
            "comparison page, including for any aggregator you are using.",
            *common,
        ],
        "howto": [
            "Start with the risk, not the return: know how much you can lose "
            "before you know what you might gain.",
            "For a first investment, a SEBI-registered mutual fund or a bank "
            "deposit covered by deposit insurance is the usual starting point.",
            *common,
        ],
        "general": [
            "We can grade promotional content, but we cannot give you personal "
            "financial advice or predict what anything will return.",
            platform,
            *common,
        ],
    }
    return by_intent.get(intent, by_intent["general"])


def _question_guidance_hi(intent: str | None, pct: float | None) -> list[str]:
    """Hindi version of the question guidance. Numbers and URLs stay as-is."""
    horizon = (
        f"उस अवधि में दोगुना होने का मतलब है हर साल चक्रवृद्धि से लगभग {pct}%। "
        "यह अंकगणित है, पूर्वानुमान नहीं: किसी ऐसे वादे को सच होने के लिए "
        "इतना देना ही होगा।"
        if pct
        else "किसी दावे का निहित रिटर्न निकालना शुद्ध अंकगणित है, पूर्वानुमान "
        "नहीं: n साल में दोगुना होने के लिए हर साल चक्रवृद्धि से लगभग "
        "(2^(1/n) - 1) चाहिए।"
    )
    platform = (
        "साथ ही यह भी देखें कि आप असल में क्या खरीद रहे हैं। ब्रोकर, "
        "एग्रीगेटर या बीमा मार्केटप्लेस एक दुकान की खिड़की है, निवेश नहीं: "
        "प्लेटफ़ॉर्म में पैसा डालने से वह बढ़ता नहीं है।"
    )
    common = [
        "SEBI-नियमित कोई उत्पाद तय, गारंटीड रिटर्न का वादा नहीं कर सकता। "
        "गारंटीड रिटर्न का दावा सबसे मज़बूत धोखाधड़ी संकेत है।",
        "जिस पर भी विचार कर रहे हैं, उसे SEBI की आधिकारिक साइट पर जाँचें: "
        f"{OFFICIAL_SOURCES['investor_site']}",
    ]
    by_intent = {
        "returns": [horizon, platform, *common],
        "safety": [
            "नियमित उत्पाद में हमेशा बाज़ार जोखिम होता है। वित्तीय संदर्भ में "
            "'सुरक्षित' का मतलब आमतौर पर इनमें से एक होता है: जमा बीमा सीमा, "
            "सरकार-समर्थित बॉन्ड, या नुकसान को असंभव बताना। पूछें कि उनका "
            "मतलब कौन-सा है।",
            "कोई व्यक्तिगत जानकारी साझा करने से पहले मध्यस्थ का नाम SEBI की "
            "मान्यता सूची में देखें: "
            f"{OFFICIAL_SOURCES['intermediary_hub']}",
            *common,
        ],
        "comparison": [
            "उत्पादों की तुलना आमतौर पर हेडलाइन नंबर पर नहीं, बल्कि टैक्स, "
            "एग्ज़िट लोड और जोखिम पर टिकती है। दर से ज़्यादा ज़्यादातर मामलों "
            "का फैसला यही तीन करते हैं।",
            "किसी तुलना पेज के बजाय AMC की साइट पर स्कीम का अपना दस्तावेज़ "
            "पढ़ें, चाहे आप जिस एग्रीगेटर का इस्तेमाल कर रहे हों।",
            *common,
        ],
        "howto": [
            "रिटर्न से नहीं, जोखिम से शुरुआत करें: क्या मिल सकता है, इससे "
            "पहले जानें कि कितना खो सकता है।",
            "पहले निवेश के लिए आमतौर पर शुरुआती बिंदु SEBI-पंजीकृत म्यूचुअल "
            "फंड या जमा बीमा वाला बैंक डिपॉज़िट होता है।",
            *common,
        ],
        "general": [
            "हम प्रचार सामग्री का आकलन कर सकते हैं, पर आपको व्यक्तिगत वित्तीय "
            "सलाह नहीं दे सकते और न यह बता सकते हैं कि किसी चीज़ का रिटर्न "
            "क्या होगा।",
            platform,
            *common,
        ],
    }
    return by_intent.get(intent, by_intent["general"])


def _summarize(
    classification: str,
    flags: set[str],
    n_claims: int,
    disclosure: bool,
    intent: str | None = None,
    text: str = "",
    categories: set[str] | None = None,
    edu_markers: list[str] | None = None,
    ui_language: str = "en",
) -> str:
    categories = categories or set()
    edu_markers = edu_markers or []
    if _normalize_ui_language(ui_language) == "hi":
        return _summarize_hi(
            classification, disclosure, intent, categories, edu_markers
        )
    names = [PERSUASION_LABELS[c] for c in sorted(categories)]

    if classification == "question":
        lead = (
            "That reads as a question rather than promotional content, so there "
            "is nothing here for us to grade"
        )
        detail = {
            "returns": " and we are not going to predict the return.",
            "safety": " and we are not going to tell you it is safe or unsafe.",
            "comparison": " and we are not going to pick a product for you.",
            "howto": " and we are not going to recommend a product.",
            "general": " and we are not going to give you financial advice.",
        }.get(intent or "general", " and we are not going to advise you.")
        return (
            f"{lead}{detail} Here is what is actually checkable. For a real "
            "verdict, paste the reel, message, or caption you want checked."
        )
    if classification == "out_of_scope":
        return (
            "This does not look like financial content, so it does not align "
            "with what Sachet checks. We only rate financial promotion vs "
            "education: investments, markets, savings, loans, insurance, or "
            "similar. Nothing was flagged. Try a reel caption, a forwarded "
            "message, or an explainer about money."
        )
    if classification == "insufficient_context":
        return (
            "There is not enough here to judge. This looks like a fragment — a "
            "forward stripped of its sender, or the middle of a longer post. "
            "No persuasion signal was found, but a short extract cannot prove "
            "there is none. Paste the full message, or the screenshot with the "
            "account name visible."
        )
    if classification == "education":
        base = "This explains rather than sells. No promotional patterns were detected"
        base += " and a risk disclaimer is present." if disclosure else "."
        if edu_markers:
            base += f" We can see teaching signals, for example: \"{edu_markers[0]}\"."
        return base
    if classification == "promotion":
        top = ", ".join(names[:3])
        return (
            f"This sells rather than teaches. It carries {len(categories)} "
            f"independent persuasion signals: {top}. More than one is what makes "
            "this a pattern rather than a single bad sentence."
        )
    # mixed: exactly one persuasion category alongside otherwise educational
    # content. Reported at low confidence on purpose.
    top = ", ".join(names[:3])
    return (
        f"Mostly educational, with one persuasive signal: {top}. One signal is "
        "a claim, not a pattern, so this is a low-confidence read — check the "
        "quoted line yourself."
    )


def _summarize_hi(
    classification: str,
    disclosure: bool,
    intent: str | None,
    categories: set[str],
    edu_markers: list[str],
) -> str:
    """Hindi summary using the same routing inputs. Teaching snippets stay verbatim."""
    names = [_persuasion_label("hi", c) for c in sorted(categories)]

    if classification == "question":
        lead = (
            "यह प्रचार सामग्री के बजाय एक सवाल लगता है, इसलिए यहाँ आकलन "
            "करने को कुछ नहीं है"
        )
        detail = {
            "returns": " और हम रिटर्न की भविष्यवाणी नहीं करेंगे।",
            "safety": " और हम इसे सुरक्षित या असुरक्षित नहीं बताएँगे।",
            "comparison": " और हम आपके लिए कोई उत्पाद नहीं चुनेंगे।",
            "howto": " और हम किसी उत्पाद की सिफारिश नहीं करेंगे।",
            "general": " और हम आपको वित्तीय सलाह नहीं देंगे।",
        }.get(intent or "general", " और हम आपको सलाह नहीं देंगे।")
        return (
            f"{lead}{detail} यहाँ वास्तव में क्या जाँचा जा सकता है। असली "
            "निर्णय के लिए वह रील, संदेश या कैप्शन चिपकाएँ जिसे जाँचना है।"
        )
    if classification == "out_of_scope":
        return (
            "यह वित्तीय सामग्री जैसी नहीं लगती, इसलिए सचेट की जाँच से मेल "
            "नहीं खाती। हम केवल वित्तीय प्रचार बनाम शिक्षा का आकलन करते हैं: "
            "निवेश, बाज़ार, बचत, कर्ज़, बीमा या ऐसी ही चीज़ें। कुछ भी चिह्नित "
            "नहीं हुआ। रील कैप्शन, आगे भेजा संदेश या पैसे पर explainer "
            "आज़माएँ।"
        )
    if classification == "insufficient_context":
        return (
            "यहाँ फैसला करने को पर्याप्त नहीं है। यह किसी अंश जैसा लगता है — "
            "भेजने वाले के बिना फॉरवर्ड, या लंबी पोस्ट का बीच का हिस्सा। कोई "
            "प्रभाव-प्रचार संकेत नहीं मिला, पर छोटा अंश यह साबित नहीं कर "
            "सकता कि कोई है ही नहीं। पूरा संदेश चिपकाएँ, या खाते का नाम "
            "दिखता स्क्रीनशॉट।"
        )
    if classification == "education":
        base = (
            "यह बेचने के बजाय समझाता है। कोई प्रचार पैटर्न नहीं मिला"
        )
        base += " और जोखिम प्रकटीकरण मौजूद है।" if disclosure else "।"
        if edu_markers:
            base += f' हमें पढ़ाने के संकेत दिखते हैं, जैसे: "{edu_markers[0]}"।'
        return base
    if classification == "promotion":
        top = ", ".join(names[:3])
        return (
            f"यह सिखाने के बजाय बेचता है। इसमें {len(categories)} स्वतंत्र "
            f"प्रभाव-प्रचार संकेत हैं: {top}। एक से ज़्यादा होना ही इसे एक "
            "खराब वाक्य के बजाय पैटर्न बनाता है।"
        )
    top = ", ".join(names[:3])
    return (
        f"ज़्यादातर शैक्षिक, साथ में एक प्रभाव-प्रचार संकेत: {top}। एक संकेत "
        "दावा है, पैटर्न नहीं, इसलिए यह कम विश्वास वाला आकलन है — उद्धृत "
        "पंक्ति खुद जाँचें।"
    )
