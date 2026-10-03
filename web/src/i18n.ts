/* Interface strings.
 *
 * Scope, stated plainly: everything the frontend owns is here -- chrome,
 * labels, verdict titles, next steps, sample names, and display names for the
 * analyzer's stable codes (flags, statuses, meter levels). Rubric prose that
 * varies per result (summaries, reasons, checklists, verification notes) is
 * localized server-side by api/analyzer.py when the UI sends ui_language;
 * quotes, rubric codes, and URLs always stay exactly as returned.
 *
 * Keys are flat and dot-namespaced. `t()` falls back to English and then to
 * the key itself, so a missing translation degrades instead of blanking. */

export type Lang = "en" | "hi";
export const LANGS: readonly Lang[] = ["en", "hi"];

const en = {
  /* chrome */
  "brand.tagline": "Promotion vs education analyzer",
  "brand.track": "Track E",
  "nav.theme": "Switch to light theme",
  "nav.themeDark": "Switch to dark theme",
  "nav.lang": "Change language",
  "notice.1": "Awareness tool, not investment advice.",
  "notice.2":
    "We never say whether a stock is good or bad. Pasted text is analyzed in memory and never stored.",

  /* hero + input */
  "hero.pill": "SANGYAN 2026",
  "hero.title1": "Does it teach,",
  "hero.title2": "or does it sell?",
  "hero.lede":
    "Paste a reel caption or message forward. We flag the exact claims and rate it: teaches, sells, or both.",
  "input.tooShort": "Please paste at least {n} characters so there is something to check.",
  "input.privacy.a":
    "Private by design: no accounts, no history, uploads discarded. Results always show uncertainty:",
  "input.privacy.em": "cannot verify",
  "input.privacy.b": "never false.",
  "img.tooBig": "That image is over 10 MB. Compress it and retry.",
  "img.err": "Could not read that image. You can still paste text.",
  "audio.tooBig": "That file is over 25 MB. Trim it under 3 minutes and retry.",
  "audio.err": "Transcription failed. You can still paste text.",
  "link.errGeneric": "Could not read that link. You can still paste the text yourself.",
  "tab.errGeneric": "Could not transcribe that tab. You can still paste the text yourself.",
  "input.tryLabel": "Try:",
  "input.samplesAria": "Try a sample",
  "input.contentLabel": "Content to analyze",
  "input.placeholder":
    "Example: Guaranteed returns! Double your money in 30 days. Join our premium group.",
  "input.countMin": "min",
  "input.countLeft": "left",
  "input.analyze": "Analyze content",
  "input.analyzing": "Analyzing",

  /* link ingest */
  "link.placeholder": "Paste a reel or video link",
  "link.aria": "Public video or reel link",
  "link.go": "Read link",
  "link.busy": "Reading…",
  "link.hint":
    "Public YouTube, Instagram, X or TikTok posts up to 3 minutes. Uses the post's own captions when it has them. We never sign in to anything, so private or login-gated posts will not work.",
  "link.errUrl": "That does not look like a link.",
  "link.errFetch": "Could not read that link.",

  /* audio attach */
  "audio.title": "Transcribed on-device with Whisper.cpp",
  "audio.attach": "Attach a short audio or video clip",
  "audio.busy": "Transcribing on-device…",
  "audio.hint": "Up to 3 minutes. Processed on this device; nothing is uploaded.",

  /* tab capture */
  "tab.title": "Listen to the tab you’re watching",
  "tab.listen": "Listen",
  "tab.gecko.title": "Tab audio needs Chrome or Edge",
  "tab.gecko.body":
    "Firefox and Zen can share a screen but not a tab's sound. Open Sachet in Chrome or Edge, or attach a clip below.",
  "tab.other.body":
    "This browser can't record a tab's sound. Use Chrome or Edge on a desktop, or attach a clip below.",
  "tab.listeningLeft": "Listening — {n}s left",
  "tab.records": "Records up to {n}s of that tab’s audio, then transcribes it. No download, no sign-in.",
  "tab.consent":
    "Captures only the tab you pick, only while you press Stop, and the audio is discarded once transcribed.",
  "tab.start": "Start listening",
  "tab.stop": "Stop",
  "tab.unsupported.title": "Tab capture isn't available here",
  "tab.unsupported.body": "Tab audio needs Chrome or Edge",
  "tab.picker": "Waiting for you to pick a tab…",
  "tab.permission": "Choose Chrome Tab and tick “Share tab audio”.",
  "tab.listening": "Hearing audio — leave the reel playing.",
  "tab.playFirst": "Play the reel with sound on. Press Stop or wait for the timer.",
  "tab.silent": "No sound yet. Check the reel is unmuted and actually playing.",
  "tab.wrapping": "Wrapping up…",
  "tab.level": "Live audio level",
  "tab.errDenied": "Permission to capture the tab was refused.",
  "tab.errNone": "No shareable tab or window was found.",
  "tab.errEmpty": "The browser produced an empty recording. Try again.",
  "tab.errStopped": "The browser stopped the capture before it started. Try again.",
  "tab.errNoRecorder":
    "This browser could not start an audio recorder. Upload the clip instead.",
  "tab.errNoAudioApi":
    "This browser has no audio recorder available. Upload a clip instead.",
  "tab.errTooShort": "That was too short to read. Let the reel play a few seconds, then try again.",

  /* verdict header */
  "verdict.result": "RESULT",
  "verdict.offline": "OFFLINE DEMO",
  "verdict.caution": "Caution",
  "verdict.confidence": "Confidence",
  "verdict.confidenceAria": "Confidence: {n} percent",
  "meter.level.low": "LOW",
  "meter.level.medium": "MEDIUM",
  "meter.level.high": "HIGH",
  "meter.scale.low": "Low",
  "meter.scale.medium": "Medium",
  "meter.scale.high": "High",
  "meter.na": "Not applicable",
  "status.present": "present",
  "status.missing": "missing",
  "status.cannot_verify": "cannot verify",
  "flag.unrealistic_returns": "unrealistic returns",
  "flag.risk_downplay": "risk downplay",
  "flag.fake_authority": "fake authority",
  "flag.paid_service_cta": "paid service cta",
  "flag.urgency_pressure": "urgency pressure",
  "flag.social_proof": "social proof",
  "flag.missing_disclosure": "missing disclosure",
  "offline.summary":
    "This content explains a financial concept but also promotes a paid group. (Offline demo response. Start the API at localhost:8000 for live rubric analysis of your {n} characters.)",
  "offline.rubric": "rubric-v1.5 (offline)",
  "report.cta": "Report on SEBI SCORES",
  "report.title": "Open SEBI SCORES to report suspected fraud",
  "verdict.signals": "Signals",
  "verdict.synthesis": "Why this reading",
  "verdict.another": "Analyze another",
  "verdict.copy": "Copy result",
  "verdict.copied": "Copied",

  /* verdict titles + blurbs, keyed by classification */
  "verdict.education.title": "Looks educational",
  "verdict.education.blurb": "Explains a concept without sales pressure.",
  "verdict.mixed.title": "Mixed: lesson plus sales pitch",
  "verdict.mixed.blurb": "Teaches something, but also pushes you to act or pay.",
  "verdict.promotion.title": "Looks promotional",
  "verdict.promotion.blurb": "Built to sell, not to teach. Treat its claims with skepticism.",
  "verdict.out_of_scope.title": "Not financial content",
  "verdict.out_of_scope.blurb": "Outside what Sachet checks, so no verdict applies.",
  "verdict.insufficient_context.title": "Not enough to judge",
  "verdict.insufficient_context.blurb": "Too little here to rule either way — paste the full post.",
  "verdict.question.title": "That’s a question, not content",
  "verdict.question.blurb": "Nothing to grade here — here’s what’s actually checkable.",

  /* panels */
  "panel.source.title": "Flagged source",
  "panel.source.none": "No sentences matched the rubric, so nothing is highlighted.",
  "panel.source.count":
    "{n} flagged claim{s} highlighted below. Quotes are verbatim. Anything we cannot check says cannot verify.",
  "panel.claims.title": "Flagged claims ({n})",
  "panel.claims.desc": "Each claim carries its rubric reason.",
  "panel.claims.clean":
    "Clean pass. No guaranteed returns, urgency tricks, or paid-group pushes detected in this text.",
  "panel.claims.outOfScope":
    "Nothing was checked here. No rubric pattern ran, because this text does not read as financial content.",
  "panel.claims.insufficient":
    "Too little text to judge. A short fragment cannot prove there is no persuasion signal in the full post.",
  "panel.guidance.title": "What to do next",
  "panel.guidance.desc": "Plain-language guidance, not advice.",
  "panel.guidance.verifyText": "What to verify for this text",
  "panel.guidance.official": "Verify on official sources",
  "panel.official.link": "Official page",
  "panel.privacy.title": "Privacy and uncertainty",
  "panel.privacy.body":
    "Your text was processed in memory and not stored. This tool spots promotional patterns. It cannot prove something true or false, confirm SEBI registration, or validate a circular from text alone. When in doubt it says cannot verify.",
  "panel.privacy.disclaimer": "This is an awareness tool, not investment advice.",

  /* claim types */
  "claimType.return_promise": "Return promise",
  "claimType.risk_denial": "Risk denial",
  "claimType.authority": "Authority claim",
  "claimType.urgency": "Urgency",
  "claimType.testimonial": "Testimonial",
  "claimType.product_pitch": "Product pitch",
  "claimType.neutral_fact": "Neutral fact",

  /* samples (names only; the sample bodies stay as written) */
  "sample.education": "Education post",
  "sample.mixed": "Mixed post",
  "sample.offTopic": "Off-topic post",
  "audio.hintFormats": "MP3, WAV, MP4 up to 3 min. Transcript lands in the box above.",
  "audio.onDevice": "ON-DEVICE",
  "audio.langLabel": "Clip language:",
  "audio.langAuto": "Auto",
  "audio.langHi": "Hindi",
  "audio.langEn": "English",
  "shot.title": "Screenshot text extracted on-device with EasyOCR",
  "shot.busy": "Reading screenshot…",
  "shot.attach": "Attach a screenshot",
  "shot.hint": "JPG, PNG, WebP up to 10 MB. Hindi and English text.",
  "rail.how.title": "How it works",
  "rail.how.desc": "Three steps, every time.",
  "rail.step1.t": "Extract claims",
  "rail.step1.d": "Exact quotes only. Nothing invented.",
  "rail.step2.t": "Apply the fixed rubric",
  "rail.step2.d": "7 flags, each with a plain-language reason.",
  "rail.step3.t": "Verdict plus caution",
  "rail.step3.d":
    "Education, Mixed, or Promotion, with Low to High caution. Text that is not financial at all returns out of scope, not a pass.",
  "rail.rubric.desc":
    "Fixed taxonomy, sourced from SEBI documents. The model only applies it.",
  "rubric.0": "Guaranteed or unrealistic returns",
  "rubric.1": "No-risk or safe language",
  "rubric.2": "Missing risk disclosure",
  "rubric.3": "Urgency or scarcity pressure",
  "rubric.4": "Fake or unverifiable authority",
  "rubric.5": "Testimonial used as evidence",
  "rubric.6": "Call to join group, app, or paid service",
  "rail.weights":
    "Weights: returns x3; risk, authority, paid-CTA x2; rest x1. Score 0-1 is Low, 2-4 Medium, 5+ High.",
  "sample.promotion": "Promotional post",

  /* errors + footer */
  "err.tooShort": "Paste a little more text so there is something to judge.",
  "err.generic": "Something went wrong. Try again.",
  "footer.built": "Sachet: promotion vs education analyzer, built for Sangyan 2026 Track E. Rubric v1.3.",
  "footer.disclaimer": "This is an awareness tool, not investment advice.",

  /* next steps, one array per classification */
  "next.education.0":
    "No promotional pattern found, but still verify any names or figures independently.",
  "next.education.1": "Check advisor names on SEBI's official intermediary list before acting.",
  "next.education.2": "Remember: even good education is not personal investment advice.",
  "next.mixed.0": "Separate the lesson from the sales pitch. Learn the concept, ignore the invite.",
  "next.mixed.1": "Do not join paid groups based on profit screenshots alone.",
  "next.mixed.2": "Verify any SEBI/NSDL notice cited here on the official circulars page.",
  "next.promotion.0": "Treat guaranteed-return promises as a red flag and pause before acting.",
  "next.promotion.1": "Never pay or share personal details with groups promising assured profits.",
  "next.promotion.2": "You can report suspected fraud on SEBI SCORES: scores.sebi.gov.in.",
  "next.out_of_scope.0":
    "Sachet only rates financial promotion vs education, so this text has nothing to grade.",
  "next.out_of_scope.1":
    "If you meant to check money content, try a reel caption, a forwarded message, or an explainer about saving and investing.",
  "next.out_of_scope.2":
    "No flags here is not a clean bill of health. For other topics use a tool built for them.",
  "next.question.0":
    "To get an actual verdict, paste the reel, message, or caption you want checked.",
  "next.question.1":
    "We can tell you whether a claim is promotional. We cannot tell you what to invest in.",
  "next.question.2":
    "For a product decision, talk to a SEBI-registered investment adviser.",
  "next.insufficient_context.0":
    "No persuasive signal was found, but a fragment cannot prove there is none.",
  "next.insufficient_context.1":
    "Paste the whole message, or a screenshot showing the account name and any handle.",
  "next.insufficient_context.2":
    "Low confidence here is deliberate: we are telling you we cannot tell.",
} as const;

export type StringKey = keyof typeof en;

const hi: Record<StringKey, string> = {
  "brand.tagline": "प्रचार बनाम शिक्षा विश्लेषक",
  "brand.track": "ट्रैक E",
  "nav.theme": "हल्की थीम पर जाएँ",
  "nav.themeDark": "गहरी थीम पर जाएँ",
  "nav.lang": "भाषा बदलें",
  "notice.1": "यह जागरूकता उपकरण है, निवेश सलाह नहीं।",
  "notice.2":
    "हम कभी नहीं कहते कि कोई शेयर अच्छी है या बुरी। चिपकाया गया टेक्स्ट मेमोरी में जाँचा जाता है और कहीं सहेजा नहीं जाता।",

  "hero.pill": "संग्यन 2026",
  "hero.title1": "क्या यह सिखाता है,",
  "hero.title2": "या यह बेचता है?",
  "hero.lede":
    "रील का कैप्शन या आगे भेजा गया संदेश चिपकाएँ। हम ठीक-ठीक दावे चिह्नित करते हैं और आकलन करते हैं: सिखाता है, बेचता है, या दोनों।",
  "input.tooShort": "जाँचने को कुछ हो, इसलिए कम से कम {n} अक्षर चिपकाएँ।",
  "input.privacy.a":
    "डिज़ाइन से निजी: कोई खाता नहीं, कोई इतिहास नहीं, अपलोड हटा दिए जाते हैं। परिणाम हमेशा अनिश्चितता दिखाते हैं:",
  "input.privacy.em": "सत्यापित नहीं",
  "input.privacy.b": "कभी false नहीं।",
  "img.tooBig": "यह इमेज 10 MB से बड़ी है। इसे छोटा करके फिर कोशिश करें।",
  "img.err": "यह इमेज पढ़ी नहीं जा सकी। आप फिर भी टेक्स्ट चिपका सकते हैं।",
  "audio.tooBig": "यह फ़ाइल 25 MB से बड़ी है। इसे 3 मिनट से कम करके फिर कोशिश करें।",
  "audio.err": "ट्रांसक्राइब विफल। आप फिर भी टेक्स्ट चिपका सकते हैं।",
  "link.errGeneric": "यह लिंक पढ़ा नहीं जा सका। आप खुद टेक्स्ट चिपका सकते हैं।",
  "tab.errGeneric": "उस टैब को ट्रांसक्राइब नहीं किया जा सका। आप खुद टेक्स्ट चिपका सकते हैं।",
  "input.tryLabel": "आज़माएँ:",
  "input.samplesAria": "नमूना आज़माएँ",
  "input.contentLabel": "जाँचने के लिए टेक्स्ट",
  "input.placeholder":
    "उदाहरण: पक्का रिटर्न! 30 दिन में पैसा दोगुना। हमारे प्रीमियम ग्रुप में जुड़ें।",
  "input.countMin": "न्यूनतम",
  "input.countLeft": "शेष",
  "input.analyze": "टेक्स्ट जाँचें",
  "input.analyzing": "जाँच हो रही है",

  "link.placeholder": "रील या वीडियो लिंक चिपकाएँ",
  "link.aria": "सार्वजनिक वीडियो या रील लिंक",
  "link.go": "लिंक पढ़ें",
  "link.busy": "पढ़ा जा रहा है…",
  "link.hint":
    "सार्वजनिक YouTube, Instagram, X या TikTok पोस्ट, 3 मिनट तक। उनके पास कैप्शन हों तो वही उपयोग होते हैं। हम कहीं लॉग इन नहीं करते, इसलिए निजी या लॉगिन-गेटेड पोस्ट काम नहीं करेंगी।",
  "link.errUrl": "यह लिंक जैसा नहीं लगता।",
  "link.errFetch": "यह लिंक पढ़ा नहीं जा सका।",

  "audio.title": "Whisper.cpp से इसी डिवाइस पर ट्रांसक्राइब",
  "audio.attach": "छोटा ऑडियो या वीडियो क्लिप जोड़ें",
  "audio.busy": "इसी डिवाइस पर ट्रांसक्राइब हो रहा है…",
  "audio.hint": "3 मिनट तक। इसी डिवाइस पर प्रोसेस होता है; कुछ भी अपलोड नहीं होता।",

  "tab.title": "जिस टैब को देख रहे हैं उसे सुनें",
  "tab.listen": "सुनें",
  "tab.gecko.title": "टैब ऑडियो के लिए Chrome या Edge चाहिए",
  "tab.gecko.body":
    "Firefox और Zen स्क्रीन तो साझा कर सकते हैं पर टैब की ध्वनि नहीं। Sachet को Chrome या Edge में खोलें, या नीचे क्लिप जोड़ें।",
  "tab.other.body":
    "यह ब्राउज़र टैब की ध्वनि रिकॉर्ड नहीं कर सकता। डेस्कटॉप पर Chrome या Edge इस्तेमाल करें, या नीचे क्लिप जोड़ें।",
  "tab.listeningLeft": "सुन रहा है — {n} सेकंड बाकी",
  "tab.records": "उस टैब का अधिकतम {n} सेकंड ऑडियो रिकॉर्ड करता है, फिर ट्रांसक्राइब करता है। कोई डाउनलोड नहीं, कोई लॉग इन नहीं।",
  "tab.consent":
    "केवल आपके चुने टैब को, केवल आपके Stop दबाने तक रिकॉर्ड होता है, और ट्रांसक्राइब होने के बाद ऑडियो हटा दिया जाता है।",
  "tab.start": "सुनना शुरू करें",
  "tab.stop": "रोकें",
  "tab.unsupported.title": "यहाँ टैब कैप्चर उपलब्ध नहीं है",
  "tab.unsupported.body": "टैब ऑडियो के लिए Chrome या Edge चाहिए",
  "tab.picker": "आपसे टैब चुनने की प्रतीक्षा हो रही है…",
  "tab.permission": "Chrome Tab चुनें और “Share tab audio” पर टिक करें।",
  "tab.listening": "ऑडियो सुनाई दे रहा है — रील चलती रहने दें।",
  "tab.playFirst": "रील ध्वनि के साथ चलाएँ। Stop दबाएँ या टाइमर की प्रतीक्षा करें।",
  "tab.silent": "अभी आवाज़ नहीं। जाँचें कि रील म्यूट नहीं है और सचमुच चल रही है।",
  "tab.wrapping": "समाप्त हो रहा है…",
  "tab.level": "लाइव ऑडियो स्तर",
  "tab.errDenied": "टैब कैप्चर की अनुमति अस्वीकार कर दी गई।",
  "tab.errNone": "साझा करने योग्य कोई टैब या विंडो नहीं मिला।",
  "tab.errEmpty": "ब्राउज़र ने खाली रिकॉर्डिंग दी। फिर कोशिश करें।",
  "tab.errStopped": "ब्राउज़र ने कैप्चर शुरू होने से पहले ही रोक दिया। फिर कोशिश करें।",
  "tab.errNoRecorder": "यह ब्राउज़र ऑडियो रिकॉर्डर शुरू नहीं कर सका। इसके बजाय क्लिप अपलोड करें।",
  "tab.errNoAudioApi": "इस ब्राउज़र में ऑडियो रिकॉर्डर उपलब्ध नहीं है। क्लिप अपलोड करें।",
  "tab.errTooShort": "यह पढ़ने के लिए बहुत छोटा था। रील को कुछ सेकंड चलने दें, फिर कोशिश करें।",

  "verdict.result": "परिणाम",
  "verdict.offline": "ऑफ़लाइन डेमो",
  "verdict.caution": "सावधानी",
  "verdict.confidence": "विश्वास",
  "verdict.confidenceAria": "विश्वास: {n} प्रतिशत",
  "meter.level.low": "कम",
  "meter.level.medium": "मध्यम",
  "meter.level.high": "अधिक",
  "meter.scale.low": "कम",
  "meter.scale.medium": "मध्यम",
  "meter.scale.high": "अधिक",
  "meter.na": "लागू नहीं",
  "status.present": "मौजूद",
  "status.missing": "नहीं मिला",
  "status.cannot_verify": "सत्यापित नहीं",
  "flag.unrealistic_returns": "गारंटीड / अवास्तविक रिटर्न",
  "flag.risk_downplay": "“कोई जोखिम नहीं” / “सुरक्षित” भाषा",
  "flag.fake_authority": "नकली / अप्रमाणित अधिकार",
  "flag.paid_service_cta": "ग्रुप / ऐप / सशुल्क सेवा में जुड़ने की बात",
  "flag.urgency_pressure": "जल्दबाज़ी या कमी का दबाव",
  "flag.social_proof": "प्रमाण के रूप में प्रशंसा-पत्र",
  "flag.missing_disclosure": "जोखिम प्रकटीकरण नहीं",
  "offline.summary":
    "यह सामग्री वित्तीय अवधारणा समझाती है, साथ ही सशुल्क ग्रुप का प्रचार भी करती है। (ऑफ़लाइन डेमो उत्तर। अपने {n} अक्षरों के लाइव रूब्रिक विश्लेषण के लिए API को localhost:8000 पर शुरू करें।)",
  "offline.rubric": "rubric-v1.5 (ऑफ़लाइन)",
  "report.cta": "SEBI SCORES पर रिपोर्ट करें",
  "report.title": "संदिग्ध धोखाधड़ी की सूचना के लिए SEBI SCORES खोलें",
  "verdict.signals": "संकेत",
  "verdict.synthesis": "यह निर्णय क्यों",
  "verdict.another": "दूसरा जाँचें",
  "verdict.copy": "परिणाम कॉपी करें",
  "verdict.copied": "कॉपी हो गया",

  "verdict.education.title": "शैक्षिक लगता है",
  "verdict.education.blurb": "बिना बिक्री के दबाव के अवधारणा समझाता है।",
  "verdict.mixed.title": "मिश्रित: पाठ के साथ बिक्री",
  "verdict.mixed.blurb": "कुछ सिखाता भी है, और कार्रवाई या भुगतान पर ज़ोर भी देता है।",
  "verdict.promotion.title": "प्रचार जैसा लगता है",
  "verdict.promotion.blurb": "बेचने के लिए बनाया गया, सिखाने के लिए नहीं। इसके दावों पर संदेह रखें।",
  "verdict.out_of_scope.title": "यह वित्तीय सामग्री नहीं है",
  "verdict.out_of_scope.blurb": "यह सचेट की जाँच से बाहर है, इसलिए कोई निर्णय लागू नहीं होता।",
  "verdict.insufficient_context.title": "फैसला करने के लिए बहुत कम",
  "verdict.insufficient_context.blurb": "दोनों तरफ से फैसला करने को यहाँ कुछ नहीं है — पूरी पोस्ट चिपकाएँ।",
  "verdict.question.title": "यह सवाल है, सामग्री नहीं",
  "verdict.question.blurb": "यहाँ आकलन करने को कुछ नहीं है — जो सचमुच जाँचा जा सकता है वह यह है।",

  "panel.source.title": "चिह्नित स्रोत",
  "panel.source.none": "कोई वाक्य रूब्रिक से मेल नहीं खाया, इसलिए कुछ भी चिह्नित नहीं है।",
  "panel.source.count":
    "नीचे {n} दावे चिह्नित हैं। उद्धरण ज्यों के त्यों हैं। जिसे हम जाँच नहीं सकते, वह “सत्यापित नहीं” कहता है।",
  "panel.claims.title": "चिह्नित दावे ({n})",
  "panel.claims.desc": "हर दावे के साथ रूब्रिक का कारण दिया गया है।",
  "panel.claims.clean":
    "साफ़। इस टेक्स्ट में पक्का रिटर्न, जल्दबाज़ी या सशुल्क ग्रुप का दबाव नहीं मिला।",
  "panel.claims.outOfScope":
    "यहाँ कुछ भी जाँचा नहीं गया। कोई रूब्रिक पैटर्न नहीं चला, क्योंकि यह टेक्स्ट वित्तीय सामग्री जैसा नहीं लगता।",
  "panel.claims.insufficient":
    "फैसला करने के लिए बहुत कम। छोटा अंश यह साबित नहीं कर सकता कि पूरी पोस्ट में कोई प्रभाव-प्रचार नहीं है।",
  "panel.guidance.title": "आगे क्या करें",
  "panel.guidance.desc": "सरल भाषा में मार्गदर्शन, सलाह नहीं।",
  "panel.guidance.verifyText": "इस टेक्स्ट में क्या जाँचें",
  "panel.guidance.official": "आधिकारिक स्रोतों पर जाँचें",
  "panel.official.link": "आधिकारिक पेज",
  "panel.privacy.title": "गोपनीयता और अनिश्चितता",
  "panel.privacy.body":
    "आपका टेक्स्ट मेमोरी में प्रोसेस हुआ और सहेजा नहीं गया। यह उपकरण प्रचार-पैटर्न पहचानता है। यह कुछ सच या असत्य साबित नहीं कर सकता, SEBI पंजीकरण की पुष्टि नहीं कर सकता, या टेक्स्ट से परिपत्रिका सत्यापित नहीं कर सकता। संदेह होने पर यह “सत्यापित नहीं” कहता है।",
  "panel.privacy.disclaimer": "यह जागरूकता उपकरण है, निवेश सलाह नहीं।",

  "claimType.return_promise": "रिटर्न का वादा",
  "claimType.risk_denial": "जोखिम से इनकार",
  "claimType.authority": "अधिकार का दावा",
  "claimType.urgency": "जल्दबाज़ी",
  "claimType.testimonial": "प्रशंसा-पत्र",
  "claimType.product_pitch": "उत्पाद बिक्री",
  "claimType.neutral_fact": "तटस्थ तथ्य",

  "sample.education": "शैक्षिक पोस्ट",
  "sample.mixed": "मिश्रित पोस्ट",
  "sample.offTopic": "बात-बाहर की पोस्ट",
  "audio.hintFormats": "MP3, WAV, MP4, 3 मिनट तक। ट्रांसक्रिप्ट ऊपर वाले बॉक्स में आ जाएगी।",
  "audio.onDevice": "ऑन-डिवाइस",
  "audio.langLabel": "क्लिप की भाषा:",
  "audio.langAuto": "स्वतः",
  "audio.langHi": "हिंदी",
  "audio.langEn": "अंग्रेज़ी",
  "shot.title": "स्क्रीनशॉट का टेक्स्ट EasyOCR से इसी डिवाइस पर निकाला जाता है",
  "shot.busy": "स्क्रीनशॉट पढ़ी जा रही है…",
  "shot.attach": "स्क्रीनशॉट जोड़ें",
  "shot.hint": "JPG, PNG, WebP, 10 MB तक। हिंदी और अंग्रेज़ी टेक्स्ट।",
  "rail.how.title": "यह कैसे काम करता है",
  "rail.how.desc": "हर बार तीन चरण।",
  "rail.step1.t": "दावे निकालें",
  "rail.step1.d": "केवल ठीक-ठीक उद्धरण। कुछ भी नहीं बनाया गया।",
  "rail.step2.t": "तय रूब्रिक लागू करें",
  "rail.step2.d": "7 संकेत, हर एक के साथ सरल भाषा में कारण।",
  "rail.step3.t": "निर्णय के साथ सावधानी",
  "rail.step3.d":
    "शिक्षा, मिश्रित या प्रचार, और Low से High तक सावधानी। जो टेक्स्ट वित्तीय है ही नहीं, उसे out of scope मिलता है — पास नहीं।",
  "rail.rubric.desc": "तय वर्गीकरण, SEBI दस्तावेज़ों से लिया गया। मॉडल इसे सिर्फ़ लागू करता है।",
  "rubric.0": "पक्का या अवास्तविक रिटर्न",
  "rubric.1": "‘कोई जोखिम नहीं’ या सुरक्षित होने का भाषा",
  "rubric.2": "जोखिम प्रकटीकरण नहीं",
  "rubric.3": "जल्दबाज़ी या कमी का दबाव",
  "rubric.4": "नकली या असत्यापित अधिकार",
  "rubric.5": "प्रशंसा-पत्र को प्रमाण के रूप में इस्तेमाल",
  "rubric.6": "ग्रुप, ऐप या सशुल्क सेवा में जुड़ने की बात",
  "rail.weights":
    "भार: रिटर्न x3; जोखिम, अधिकार, सशुल्क-CTA x2; शेष x1। स्कोर 0-1 = कम, 2-4 = मध्यम, 5+ = अधिक।",
  "sample.promotion": "प्रचार पोस्ट",

  "err.tooShort": "फैसला करने के लिए थोड़ा और टेक्स्ट चिपकाएँ।",
  "err.generic": "कुछ गड़बड़ हो गई। फिर कोशिश करें।",
  "footer.built": "सचेट: प्रचार बनाम शिक्षा विश्लेषक, संग्यन 2026 ट्रैक E के लिए। रूब्रिक v1.3.",
  "footer.disclaimer": "यह जागरूकता उपकरण है, निवेश सलाह नहीं।",

  "next.education.0":
    "कोई प्रचार पैटर्न नहीं मिला, फिर भी किसी भी नाम या आँकड़े की स्वतंत्र रूप से जाँच करें।",
  "next.education.1": "कार्रवाई से पहले सलाहकार का नाम SEBI की आधिकारिक मध्यस्थ सूची में देखें।",
  "next.education.2": "याद रखें: अच्छी शिक्षा भी व्यक्तिगत निवेश सलाह नहीं होती।",
  "next.mixed.0": "पाठ को बिक्री से अलग करें। अवधारणा सीखें, न्योता छोड़ दें।",
  "next.mixed.1": "केवल मुनाफे के स्क्रीनशॉट के आधार पर सशुल्क ग्रुप में न जुड़ें।",
  "next.mixed.2": "यहाँ उद्धृत SEBI/NSDL सूचना को आधिकारिक परिपत्रिका पेज पर जाँचें।",
  "next.promotion.0": "पक्का रिटर्न के वादे को लाल झंडा मानें और कार्रवाई से पहले रुकें।",
  "next.promotion.1": "उन ग्रुप में कभी पैसा न दें और न व्यक्तिगत जानकारी साझा करें जो पक्का मुनाफा देने का वादा करें।",
  "next.promotion.2": "संदिग्ध धोखाधड़ी की सूचना SEBI SCORES पर दे सकते हैं: scores.sebi.gov.in।",
  "next.out_of_scope.0":
    "सचेट केवल वित्तीय प्रचार बनाम शिक्षा को आकलन करता है, इसलिए इस टेक्स्ट को आकलन करने को कुछ नहीं है।",
  "next.out_of_scope.1":
    "यदि आप पैसे से जुड़ी सामग्री जाँचना चाहते थे, तो रील कैप्शन, आगे भेजा संदेश, या बचत और निवेश पर एक explainer आज़माएँ।",
  "next.out_of_scope.2":
    "यहाँ कोई चिह्न नहीं होना स्वस्थ प्रमाणपत्र नहीं है। दूसरे विषयों के लिए उसी के लिए बना उपकरण इस्तेमाल करें।",
  "next.question.0":
    "वास्तविक निर्णय पाने के लिए वह रील, संदेश या कैप्शन चिपकाएँ जिसे जाँचना है।",
  "next.question.1":
    "हम बता सकते हैं कि कोई दावा प्रचार है या नहीं। यह नहीं बता सकते कि आपको किसमें निवेश करना चाहिए।",
  "next.question.2":
    "किसी उत्पाद पर निर्णय के लिए SEBI-पंजीकृत निवेश सलाहकार से बात करें।",
  "next.insufficient_context.0":
    "कोई प्रभाव-प्रचार संकेत नहीं मिला, पर अंश यह साबित नहीं कर सकता कि कोई है ही नहीं।",
  "next.insufficient_context.1":
    "पूरा संदेश चिपकाएँ, या खाते का नाम और हैंडल दिखाता स्क्रीनशॉट।",
  "next.insufficient_context.2":
    "यहाँ कम विश्वास जानबूझकर है: हम यह कह रहे हैं कि हम नहीं बता सकते।",
};

const DICTIONARIES: Record<Lang, Record<StringKey, string>> = { en, hi };

/* Substitutes {n} and {s} so counts can stay grammatically correct in
   Hindi, where pluralisation works differently than in English. */
function interpolate(template: string, vars?: Record<string, string | number>): string {
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (whole, key: string) =>
    key in vars ? String(vars[key]) : whole
  );
}

export function makeT(lang: Lang) {
  return (key: string, vars?: Record<string, string | number>): string => {
    const table = DICTIONARIES[lang] as Record<string, string>;
    // Falls back to English, then to the key. A missing translation should
    // degrade to readable text, never to a blank label.
    const value = table[key] ?? (DICTIONARIES.en as Record<string, string>)[key] ?? key;
    return interpolate(value, vars);
  };
}

export type T = ReturnType<typeof makeT>;