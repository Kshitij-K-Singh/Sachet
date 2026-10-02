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
