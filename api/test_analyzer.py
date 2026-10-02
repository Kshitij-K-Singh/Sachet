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
