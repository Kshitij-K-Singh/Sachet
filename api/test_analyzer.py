"""Baseline analyzer tests — run with:  python -m pytest -q"""

from analyzer import analyze_text


def test_promotion_sample():
    text = (
        "Guaranteed returns! Double your money in 30 days, 100% safe, no risk. "
        "Join our premium Telegram group now, limited seats, hurry!"
    )
    out = analyze_text(text)
    assert out["classification"] == "promotion"
    assert out["caution_level"] == "high"
    # every claim quote must appear verbatim in the source
    for c in out["claims"]:
        assert c["quote"][:60] in text
    assert "unrealistic_returns" in out["flags"]
    assert "paid_service_cta" in out["flags"]
    assert "missing_disclosure" in out["flags"]


def test_education_sample():
    text = (
        "A mutual fund pools money from many investors to buy stocks and bonds. "
        "Mutual fund investments are subject to market risks. "
        "This is for educational purposes only and is not investment advice. "
        "Please consult a SEBI-registered investment adviser."
    )
    out = analyze_text(text)
    assert out["classification"] == "education"
    assert out["caution_level"] == "low"
    assert out["claims"] == []
    assert out["verification"][1]["status"] == "present"


def test_mixed_sample():
    text = (
        "Compounding means your returns also earn returns over time. "
        "My student earned 2 lakh profit last month, DM me to join my premium group!"
    )
    out = analyze_text(text)
    assert out["classification"] in ("mixed", "promotion")
    assert out["caution_level"] in ("medium", "high")


def test_forward_return_promise_with_horizon_is_promotion():
    # User-reported miss: "return of 60% over the next three months" used the
    # noun-first order, which the old %-before-noun pattern never matched.
    text = (
        "I feel if I buy stocks of policy without today for at least 100 rupees, "
        "then I will get a return of 60% over the next three months."
    )
    out = analyze_text(text)
    assert out["classification"] == "promotion"
    assert out["caution_level"] == "high"
    assert "unrealistic_returns" in out["flags"]


def test_horizon_requiring_return_promise_variants():
    for text in (
        "Buy today and get a return of 60% in 3 months with zero risk.",
        "Invest now, this gives you a profit of 90% within 6 weeks.",
        "Aapko 3 mahine me 60 percent ka return milega, aaj hi kharido.",
    ):
        assert "unrealistic_returns" in analyze_text(text)["flags"], text


def test_long_horizon_return_facts_stay_education():
    # The horizon token is the discriminator: edu-0003's "12% annualised
    # returns over very long periods" must not be read as a promise.
    text = (
        "Equity funds have delivered around 12% annualised returns over very long "
        "periods, but yearly returns swing widely and capital is at risk."
    )
    assert analyze_text(text)["classification"] == "education"


def test_off_topic_text_is_out_of_scope_not_education():
    # Random chatter must not get a confident "education" verdict.
    out = analyze_text("I love pizza and football, we went to the park yesterday afternoon")
    assert out["classification"] == "out_of_scope"
    assert out["caution_level"] == "not_applicable"
    assert out["caution_score"] == 0
    assert out["claims"] == []
    assert "does not look like financial" in out["summary"].lower()


def test_out_of_scope_survives_bilingual_off_topic_text():
    for text in (
        "It is raining heavily in Mumbai today and the roads are flooded",
        "Mix two cups of flour with one cup sugar and bake at 180 degrees",
        "आज मौसम बहुत ठंडा है और बारिश हो रही है",
    ):
        assert analyze_text(text)["classification"] == "out_of_scope", text


def test_flags_keep_promotional_text_in_scope_even_without_finance_words():
    # Promo language is topic-agnostic; a scam caption with no finance
    # vocabulary must still be rated, never dismissed as out of scope.
    out = analyze_text("Guaranteed 10x returns, join our premium group now, hurry, limited seats")
    assert out["classification"] in ("mixed", "promotion")
    assert out["caution_level"] != "not_applicable"


def test_finance_content_without_flags_stays_in_scope():
    for text in (
        "A mutual fund pools money from many investors to buy stocks and bonds.",
        "Paisa kaise lagaye? Mutual fund SIP start karo, pehle documents padho",
        "म्यूचुअल फंड में निवेश करने से पहले सभी दस्तावेज ध्यान से पढ़ें",
        "Stocks can go down as well as up",
    ):
        assert analyze_text(text)["classification"] == "education", text


def test_verbatim_validation():
    out = analyze_text("Hello world, nothing financial here at all, just chatting.")
    for c in out["claims"]:
        assert c["quote"] in "Hello world, nothing financial here at all, just chatting."


def test_disclaimer_always_present():
    out = analyze_text("Guaranteed 10x returns, join now, limited offer seats left today!")
    assert "not investment advice" in out["disclaimer"].lower()
    assert all(v["status"] in ("present", "missing", "cannot_verify") for v in out["verification"])


def test_verification_links_are_specific_official_pages():
    # No bare-homepage links: every URL must be a verified official page.
    out = analyze_text("Guaranteed 10x returns, join now, limited offer seats left today!")
    urls = [v["url"] for v in out["verification"]]
    assert len(urls) == 3
    for u in urls:
        assert u.startswith("https://www.sebi.gov.in/") or u.startswith("https://investor.sebi.gov.in/")
        assert u.rstrip("/") != "https://www.sebi.gov.in"
    by_label = {v["label"]: v for v in out["verification"]}
    assert "CIR/2023/51" in by_label["Official circular / notice"]["note"]
    assert "intmId=13" in by_label["SEBI registration"]["url"]


def test_standard_mf_warning_counts_as_disclosure():
    text = (
        "This fund aims to grow your money over time. Mutual fund investments "
        "are subject to market risks, read all scheme related documents carefully."
    )
    out = analyze_text(text)
    assert out["verification"][1]["status"] == "present"


def test_every_flag_cites_a_verified_source():
    from analyzer import FLAG_SOURCES

    out = analyze_text(
        "Guaranteed returns! Double your money, 100% safe, no risk. "
        "Join our premium Telegram group now, limited seats! "
        "My student earned 2 lakh profit from my secret SEBI insider trick."
    )
    assert out["flags"], "expected flags on a fully promotional sample"
    for f in out["flags"]:
        assert f in FLAG_SOURCES, f"flag {f} has no sourced citation"


# ---------------------------------------------------------------- questions

def test_user_question_is_not_graded_as_education():
    # The reported bug: a personal investment question scored 0 and came back
    # as "straightforward financial education", which graded content nobody
    # submitted. A question is not content.
    text = "if i invest 100 rupees in policy bazaar will it double in next 2 years"
    out = analyze_text(text)
    assert out["classification"] == "question"
    assert out["caution_level"] == "not_applicable"
    assert out["caution_score"] == 0
    assert out["claims"] == []
    assert out["guidance"]


def test_question_guidance_shows_doubling_arithmetic_not_a_forecast():
    text = "if i invest 100 rupees in policy bazaar will it double in next 2 years"
    out = analyze_text(text)
    joined = " ".join(out["guidance"])
    # 2**(1/2) - 1 = 41.4% per year. Arithmetic, and it must say so.
    assert "41%" in joined
    assert "arithmetic, not a forecast" in joined
    # Never a promise, never advice.
    for banned in ("guaranteed return of", "we recommend", "you should invest"):
        assert banned not in joined.lower()
    assert "not investment advice" in out["disclaimer"].lower()


def test_doubling_math_across_horizons():
    from analyzer import _doubling_math

    assert _doubling_math("will it double in 2 years") == "41"
    assert _doubling_math("will it double in 1 year") == "100"
    assert _doubling_math("will it double in 5 years") == "15"
    assert _doubling_math("will it double") is None
    assert _doubling_math("is my mutual fund good") is None


def test_questions_detected_across_languages_and_intents():
    cases = {
        "will my mutual fund double in 2 years?": "returns",
        "kya policy bazaar me invest karna safe hai?": "safety",
        "how do I start investing in mutual funds?": "howto",
        "which mutual fund is better for long term?": "comparison",
        "क्या म्यूचुअल फंड में निवेश करना सुरक्षित है?": "safety",
    }
    for text, intent in cases.items():
        out = analyze_text(text)
        assert out["classification"] == "question", text
        assert out["guidance"], text


def test_promise_framing_is_still_graded_not_treated_as_a_question():
    # The near-miss: a first-person promise with the same numbers is content,
    # not a question, and must keep its promotion verdict.
    text = (
        "I feel if I buy stocks of policy without today for at least 100 rupees, "
        "then I will get a return of 60% over the next three months."
    )
    out = analyze_text(text)
    assert out["classification"] == "promotion"
    assert out["caution_level"] == "high"
    assert "unrealistic_returns" in out["flags"]
    assert out["guidance"] == []


def test_question_asking_to_grade_a_pitch_stays_on_rubric_path():
    # "should I join their guaranteed 10x group?" is a question about a promo.
    # The user wants the pitch graded, so the rubric must answer, not deflect.
    text = "should I join their group for guaranteed 10x returns?"
    out = analyze_text(text)
    assert out["classification"] != "question"
    assert "unrealistic_returns" in out["flags"]


def test_question_verification_note_does_not_demand_a_disclaimer():
    out = analyze_text("will my mutual fund double in 2 years?")
    disclosure = next(v for v in out["verification"] if v["label"] == "Risk disclosure")
    assert "no risk disclaimer is expected" in disclosure["note"]
    assert "No risk disclaimer found" not in disclosure["note"]


def test_non_financial_question_stays_out_of_scope():
    # The question branch requires finance vocabulary; otherwise this would
    # swallow the out_of_scope gate entirely.
    out = analyze_text("how do I change a bicycle tyre at home?")
    assert out["classification"] == "out_of_scope"
    assert out["guidance"] == []


def test_question_plus_instructions_is_content_not_a_question():
    # Regression: captions are often phrased as a question then give the
    # lesson. That is content we must grade, not a question to deflect.
    text = "Paisa kaise lagaye? Mutual fund SIP start karo, pehle documents padho"
    out = analyze_text(text)
    assert out["classification"] == "education"
    assert out["guidance"] == []


def test_no_dataset_item_is_reclassified_as_a_question():
    # Regression guard for the real risk here: a question pattern loose enough
    # to catch promotional copy would silently corrupt the rubric's dataset.
    import glob
    import json

    seen = 0
    for path in sorted(glob.glob("data/*.jsonl")):
        for line in open(path):
            if not line.strip():
                continue
            row = json.loads(line)
            seen += 1
            assert analyze_text(row["text"])["classification"] != "question", (
                f"{path}: question branch swallowed a dataset item"
            )
    assert seen >= 250, f"expected the full corpus, only saw {seen} items"


# ------------------------------------------------- evidence model (v1.5)
#
# The v1.3/v1.4 weighted score ladder made the verdict a function of which
# keywords happened to be written down. Measured example:
#   "will it double"    -> 0 points  -> question
#   "will it triple"    -> 3 + 1     -> mixed
#   "will it quadruple" -> 0 points  -> question   (not in the pattern list)
# A more extreme claim produced a gentler verdict because one word was absent
# from a regex. v1.5 counts independent persuasion CATEGORIES instead.

def test_verdict_is_invariant_to_synonym_choice():
    # The reported bug: swapping double -> triple flipped the verdict.
    base = "if i invest 100 rupees in policy bazaar will it {} in next 2 years"
    seen = {
        analyze_text(base.format(v))["classification"]
        for v in ("double", "triple", "quadruple", "quintuple", "10x", "multiply")
    }
    assert seen == {"question"}, seen


def test_repeating_one_tactic_cannot_manufacture_a_pattern():
    # Volume is not evidence. Five return-promise keywords are still one
    # tactic, so this must stay mixed at low confidence, never promotion.
    base = "Guaranteed returns, double your money, 10x returns, fixed profit."
    results = []
    for _ in range(5):
        r = analyze_text(base)
        results.append((r["classification"], len(r["persuasion_categories"]), r["confidence"]))
        base += " Guaranteed returns again."
    assert {c for c, _, _ in results} == {"mixed"}, results
    assert {n for _, n, _ in results} == {1}
    assert len({conf for _, _, conf in results}) == 1, "confidence drifted with repetition"


def test_a_second_independent_tactic_escalates_to_promotion():
    one = "Guaranteed returns, double your money, 10x returns, fixed profit."
    two = one + " Join our premium Telegram group now."
    assert analyze_text(one)["classification"] == "mixed"
    r = analyze_text(two)
    assert r["classification"] == "promotion"
    assert len(r["persuasion_categories"]) == 2
    assert r["confidence"] > analyze_text(one)["confidence"]


def test_promotion_confidence_is_higher_than_mixed():
    assert analyze_text(
        "Guaranteed returns, double your money. Join our group now."
    )["confidence"] > analyze_text(
        "Guaranteed returns, double your money."
    )["confidence"]


def test_one_category_never_reaches_promotion():
    # Each sample below trips exactly ONE tactic, so the highest verdict any
    # can earn is mixed, at low confidence. Samples that trip two (e.g. a CTA
    # plus scarcity) are correctly promotion -- that is what counting
    # categories buys, and why these were chosen by measurement not by eye.
    samples = {
        "Guaranteed returns, double your money in 30 days.": "return_promise",
        "This is completely risk free and 100% safe for everyone.": "risk_denial",
        "My ex-SEBI friend told me the secret trick.": "authority_claim",
        "My student earned 2 lakh profit last month, join my paid group.": None,
    }
    # "Limited seats left, act before midnight" and "My student earned 2 lakh
    # profit last month" were removed as single-category samples: the v1.5
    # pattern expansion (seat counts, member counts) makes them legitimately
    # multi-category. Asserting they stay single-category would pin the
    # weaker patterns in place.
    del samples["My student earned 2 lakh profit last month, join my paid group."]
    for text, expected_category in (
        ("Guaranteed returns, double your money in 30 days.", "return_promise"),
        ("This is completely risk free and 100% safe for everyone.", "risk_denial"),
        ("My ex-SEBI friend told me the secret trick.", "authority_claim"),
    ):
        out = analyze_text(text)
        assert out["persuasion_categories"] == [expected_category], (
            text, out["persuasion_categories"]
        )
        assert out["classification"] == "mixed", (text, out["classification"])
        assert out["confidence"] <= 0.55, (text, out["confidence"])


def test_red_flags_carry_verbatim_evidence():
    text = (
        "Guaranteed returns! Double your money in 30 days, 100% safe, no risk. "
        "Join our premium Telegram group now, limited seats!"
    )
    out = analyze_text(text)
    assert out["red_flags"], "expected structured red flags"
    for f in out["red_flags"]:
        assert f["category"] in ("return_promise", "risk_denial", "authority_claim",
                                 "commercial_cta", "urgency", "social_proof")
        assert f["label"] and f["quote"]
        assert f["quote"][:40] in text, "red flag quote must be verbatim"


def test_what_to_verify_is_specific_to_fired_categories():
    out = analyze_text(
        "Join our premium Telegram group now for guaranteed 10x returns!"
    )
    joined = " ".join(out["what_to_verify"]).lower()
    assert "telegram" in joined or "personal details" in joined
    assert "sebi" in joined, "must always give the regulator pointer"
    # A clean text must not claim a scam check is needed.
    clean = analyze_text(
        "A mutual fund pools money from many investors to buy stocks and bonds."
    )
    assert not clean["red_flags"]
    assert "not a clean bill of health" in " ".join(clean["what_to_verify"]).lower()


def test_scope_and_label_axes_are_consistent():
    promo = analyze_text(
        "Guaranteed returns! Double your money. Join our premium Telegram group now!"
    )
    assert promo["scope"] == "in_scope" and promo["label"] == "promotion"
    edu = analyze_text(
        "A mutual fund pools money from many investors to buy stocks and bonds."
    )
    assert edu["scope"] == "in_scope" and edu["label"] == "educational"
    # mixed is educational-with-signals, not a third opinion
    mix = analyze_text("Guaranteed returns, double your money.")
    assert mix["classification"] == "mixed" and mix["label"] == "educational"
    assert mix["red_flags"]
    off = analyze_text("how do I cook pasta?")
    assert off["scope"] == "out_of_scope" and off["label"] == "unclear"
    assert off["caution_level"] == "not_applicable"


def test_abstentions_never_claim_high_confidence():
    for text in (
        "will it triple in 2 years?",
        "how do I cook pasta?",
        "guaranteed returns, double your money.",
        "Stocks can go down as well as up",
    ):
        out = analyze_text(text)
        assert out["confidence"] <= 0.55, (text, out["confidence"])


def test_fragment_is_insufficient_context_not_education():
    # A stripped WhatsApp forward with nothing in it must not read as clean.
    out = analyze_text("check this out")
    assert out["classification"] == "out_of_scope"  # no finance vocabulary


def test_commercial_question_about_a_pitch_is_graded_not_deflected():
    out = analyze_text("should I join their group for guaranteed 10x returns?")
    assert out["classification"] != "question"
    assert out["persuasion_categories"]


def test_ordinary_short_statement_is_not_called_insufficient():
    # Length gate is for fragments, not for short posts.
    out = analyze_text("Stocks can go down as well as up")
    assert out["classification"] == "education"


def test_corpus_agreement_stays_above_ninety_percent():
    # Guards the v1.5 redesign against silently degrading the demo. Scoped
    # to the ORIGINAL batch 1+2 corpus: batch 3 deliberately includes 33
    # promotion items the rubric under-detects, so folding it in here would
    # measure a different (and intentionally harder) thing. The batch 3 and
    # held-out numbers live in ml/README.md.
    import json

    originals = [
        "education.jsonl", "education2.jsonl",
        "mixed.jsonl", "mixed2.jsonl",
        "promotion.jsonl", "promotion2.jsonl",
    ]
    hits = 0
    total = 0
    for name in originals:
        for line in open(f"data/{name}"):
            if not line.strip():
                continue
            row = json.loads(line)
            total += 1
            if analyze_text(row["text"])["classification"] == row["label"]:
                hits += 1
    assert total >= 250
    assert hits / total >= 0.9, f"corpus agreement dropped to {hits}/{total}"


def test_heldout_set_can_never_reach_training():
    # Structural guarantee, not a convention: the held-out files are not in
    # CANDIDATE_FILES, so load_items cannot return them.
    from ml import dataset

    train, _ = dataset.load_items()
    heldout = dataset.load_heldout()
    dataset.assert_disjoint(train, heldout)
    assert len(heldout) >= 300, f"held-out set shrank to {len(heldout)}"
    train_ids = {i["id"] for i in train}
    assert not (train_ids & {i["id"] for i in heldout})


def test_both_new_batches_are_loadable():
    from ml import dataset

    train, _ = dataset.load_items()
    assert len(train) >= 400, f"train pool is only {len(train)}"
    langs = {i["lang"] for i in train}
    assert {"en", "hi", "hinglish"} <= langs


# ------------------------------------------- Devanagari question detection
# Two real bugs found by batch 3, both from ASCII \b not creating word
# boundaries in Devanagari and from Hindi putting the wh-word mid-sentence.

def test_devanagari_because_is_not_a_question():
    # क्यों is a prefix of क्योंकि ("because"). ASCII \b does not separate
    # them, so the bare marker matched declarative Hindi.
    from analyzer import _is_question

    text = (
        "क्रेडिट कार्ड का लाभ ज्यादातर लोगों के लिए जोखिम से ज्यादा नुकसानदेह होता है, "
        "क्योंकि बकाया रकम पर ब्याज दर आपकी मंज़ूरी से बहुत अधिक हो सकती है।"
    )
    assert not _is_question(text)
    assert analyze_text(text)["classification"] != "question"


def test_devanagari_wh_word_mid_sentence_is_a_noun_clause():
    # "देखें कि बेंचमार्क क्या है" = "check WHAT the benchmark is".
    # A mid-clause wh-word is a noun clause inside a declarative sentence.
    from analyzer import _is_question

    text = (
        "म्यूचुअल फंड में पैसा लगाने से पहले यह देखें कि उसका बेंचमार्क क्या है और "
        "उसकी एक्सपेंस रेशियो कितनी है, क्योंकि यही लंबी अवधि में फर्क तय करती है।"
    )
    assert not _is_question(text)


def test_devanagari_questions_detected_at_head_and_tail():
    from analyzer import _is_question

    assert _is_question("क्या म्यूचुअल फंड में निवेश करना सुरक्षित है?")
    assert _is_question("क्या म्यूचुअल फंड सुरक्षित है")
    assert _is_question("कितना रिटर्न मिलेगा ये कैसे पता चलेगा?")


def test_hindi_ui_language_localizes_display_strings_only():
    text = (
        "Guaranteed returns! Double your money in 30 days, 100% safe, no risk. "
        "Join our premium Telegram group now, limited seats, hurry!"
    )
    en = analyze_text(text, ui_language="en")
    hi = analyze_text(text, ui_language="hi")

    assert hi["classification"] == en["classification"] == "promotion"
    assert hi["flags"] == en["flags"]
    assert hi["claims"][0]["quote"] == en["claims"][0]["quote"]
    assert hi["verification"][0]["url"] == en["verification"][0]["url"]

    assert "बेचता" in hi["summary"]
    assert "This sells rather than teaches" in en["summary"]
    assert hi["claims"][0]["reason"] != en["claims"][0]["reason"]
    assert hi["flag_labels"] != en["flag_labels"]
    assert hi["verification"][0]["label"] == "SEBI पंजीकरण"
    assert hi["disclaimer"] == "यह जागरूकता उपकरण है, निवेश सलाह नहीं।"


def test_unknown_ui_language_falls_back_to_english():
    out = analyze_text("Guaranteed returns, join now.", ui_language="xx")
    assert out["summary"].startswith("This sells rather than teaches.")
