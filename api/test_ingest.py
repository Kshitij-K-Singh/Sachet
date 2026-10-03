"""Paste-a-link ingest tests.

Everything here is offline: the SSRF guard is exercised by monkeypatching DNS,
and the yt-dlp layers are exercised by monkeypatching the subprocess boundary.
No test in this file touches the network -- that is the point, because a test
that reaches YouTube is a test that breaks when YouTube changes.
"""

import ipaddress
import subprocess

import pytest

import ingest
from errors import PipelineError
from ingest import (
    MAX_ANALYZE_CHARS,
    _dedupe_rolling,
    _friendly_ytdlp_error,
    _ip_is_blocked,
    parse_vtt,
    validate_url,
)

# --------------------------------------------------------------------- SSRF


@pytest.mark.parametrize(
    "raw,reason",
    [
        ("http://127.0.0.1:8000/api/meta", "loopback service"),
        ("http://169.254.169.254/latest/meta-data/", "cloud metadata"),
        ("http://[::1]/", "IPv6 loopback"),
        ("http://[::ffff:127.0.0.1]/", "IPv4-mapped loopback bypass"),
        ("http://10.0.0.5/", "private range"),
        ("http://192.168.1.1/admin", "private range"),
        ("http://172.16.9.9/", "private range"),
        ("http://0.0.0.0/", "unspecified"),
        ("file:///etc/passwd", "local file scheme"),
        ("gopher://youtube.com/", "non-http scheme"),
        ("http://user:pass@evil.test/", "embedded credentials"),
    ],
)
def test_blocked_addresses_and_schemes(raw, reason):
    """The URL never gets as far as a socket. Allowlist fires first."""
    with pytest.raises(PipelineError):
        ingest._resolve_public_url(raw)


@pytest.mark.parametrize(
    "host",
    ["notyoutube.com", "youtube.com.evil.test", "evil-youtube.com", "x.com.attacker.io"],
)
def test_host_allowlist_suffix_is_anchored(host):
    """A naive endswith() check would let all of these through."""
    assert ingest._host_allowed(host) is False


@pytest.mark.parametrize(
    "host",
    ["youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "X.COM", "instagram.com."],
)
def test_host_allowlist_accepts_real_platforms(host):
    assert ingest._host_allowed(host) is True


def test_bare_host_is_upgraded_to_https():
    url, host = validate_url("youtube.com/watch?v=abc")
    assert url == "https://youtube.com/watch?v=abc"
    assert host == "youtube.com"


def test_allowed_host_resolving_private_is_still_rejected(monkeypatch):
    """DNS poisoning / hijack defence: allowlisted name, private answer."""
    monkeypatch.setattr(
        ingest.socket,
        "getaddrinfo",
        lambda *a, **k: [(2, 1, 6, "", ("169.254.169.254", 0))],
    )
    with pytest.raises(PipelineError):
        ingest._resolve_public_url("https://www.youtube.com/watch?v=abc")


def test_public_resolution_passes_the_ip_gate(monkeypatch):
    monkeypatch.setattr(
        ingest.socket,
        "getaddrinfo",
        lambda *a, **k: [(2, 1, 6, "", ("142.250.185.14", 0))],
    )
    url, host = ingest._resolve_public_url("https://www.youtube.com/watch?v=abc")
    assert host == "www.youtube.com"
    assert url.startswith("https://")


def test_unresolvable_host_is_a_clean_400(monkeypatch):
    def boom(*a, **k):
        raise ingest.socket.gaierror("nope")

    monkeypatch.setattr(ingest.socket, "getaddrinfo", boom)
    with pytest.raises(PipelineError) as e:
        ingest._resolve_public_url("https://www.youtube.com/watch?v=abc")
    assert e.value.status == 400


@pytest.mark.parametrize(
    "addr",
    [
        "127.0.0.1",
        "169.254.169.254",
        "10.1.2.3",
        "100.64.0.1",       # CGNAT: routable-looking, must stay blocked
        "198.18.0.1",       # benchmarking range
        "::1",
        "::ffff:10.0.0.1",  # IPv4-mapped private
        "2002:7f00:0001::",  # 6to4-wrapped loopback
        "fe80::1",
        "fc00::1",
    ],
)
def test_ip_is_blocked(addr):
    assert _ip_is_blocked(ipaddress.ip_address(addr)) is True


def test_public_ip_is_not_blocked():
    assert _ip_is_blocked(ipaddress.ip_address("142.250.185.14")) is False


# ------------------------------------------------------------------ captions


VTT = """WEBVTT
Kind: captions
Language: en

00:00:00.000 --> 00:00:02.000
<c>guaranteed returns</c>

00:00:02.000 --> 00:00:04.000
double your money

00:00:04.000 --> 00:00:06.000
double your money in thirty days &amp; risk free

NOTE this is a comment

00:00:06.000 --> 00:00:08.000
join our premium group
"""


def test_parse_vtt_strips_meta_cues_and_tags():
    text = parse_vtt(VTT)
    assert "WEBVTT" not in text
    assert "-->" not in text
    assert "<c>" not in text
    assert "&amp;" not in text
    assert "&" in text  # unescaped


def test_parse_vtt_collapses_rolling_duplicates():
    """Without dedupe the transcript reads 'double your money' twice."""
    text = parse_vtt(VTT)
    assert text == (
        "guaranteed returns double your money in thirty days & risk free "
        "join our premium group"
    )


def test_dedupe_keeps_a_genuine_later_repeat():
    lines = ["join now", "offer ends", "join now"]
    assert _dedupe_rolling(lines) == "join now offer ends join now"


def test_dedupe_slides_the_window_on_extension():
    assert _dedupe_rolling(["compounding means", "compounding means your returns"]) == (
        "compounding means your returns"
    )


def test_parse_vtt_empty_is_empty():
    assert parse_vtt("WEBVTT\n\n") == ""


# --------------------------------------------------------------- yt-dlp errors


@pytest.mark.parametrize(
    "stderr,expected",
    [
        ("ERROR: [youtube] abc: Private video. Sign in if you've been granted access",
         "private"),
        ("ERROR: [generic] login required", "login"),
        ("ERROR: Unsupported URL: https://example.com/x", "cannot read"),
        ("ERROR: Video unavailable", "unavailable"),
        ("ERROR: age restricted", "age-restricted"),
    ],
)
def test_ytdlp_errors_become_actionable_copy(stderr, expected):
    msg = _friendly_ytdlp_error(stderr)
    assert expected in msg.lower()


def test_ytdlp_error_never_echoes_the_url():
    """The caller's URL must not ride out through an error body."""
    hostile = "https://evil.test/'; DROP TABLE--"
    msg = _friendly_ytdlp_error(f"ERROR: {hostile} not found")
    assert "evil.test" not in msg
    assert "DROP TABLE" not in msg


# ------------------------------------------------------------------ contract


def test_captions_survive_a_partial_yt_dlp_failure(monkeypatch, tmp_path):
    """Regression: yt-dlp exits non-zero when a requested language 429s, but it
    has already written the tracks it did fetch. Trusting the return code
    discarded a good Hindi track and forced an expensive download."""

    def fake_ytdlp(args, timeout, what):
        (tmp_path / "caps.hi.vtt").write_text(
            "WEBVTT\n\n00:00:00.000 --> 00:00:02.000\n"
            "ये पैसे दस दिन में दोगुने हो जाएंगे\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(args, 1, "", "HTTP Error 429")

    monkeypatch.setattr(ingest, "_ytdlp", fake_ytdlp)
    out = ingest._fetch_captions("https://youtu.be/abc", tmp_path)
    assert out is not None, "a usable track on disk must win over a non-zero exit"
    assert "पैसे" in out


def test_one_rate_limited_language_does_not_block_the_other(monkeypatch, tmp_path):
    """The bug that made this fall back to a 30s CPU transcription: yt-dlp
    fails the whole invocation if any one requested language 429s, so asking for
    "hi.*,en.*" together threw away a perfectly good English track."""
    requested: list[str] = []

    def fake_ytdlp(args, timeout, what):
        lang = args[args.index("--sub-langs") + 1]
        requested.append(lang)
        if lang.startswith("hi"):
            # Hindi rate-limited: nothing written.
            return subprocess.CompletedProcess(args, 1, "", "HTTP Error 429")
        (tmp_path / "caps.en.vtt").write_text(
            "WEBVTT\n\n00:00:00.000 --> 00:00:02.000\ndouble your money\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(ingest, "_ytdlp", fake_ytdlp)
    out = ingest._fetch_captions("https://youtu.be/abc", tmp_path)
    assert out == "double your money"
    assert requested == ["hi.*", "en.*"], "falls through to the next language"


def test_hint_orders_the_language_attempts(monkeypatch, tmp_path):
    """An explicit hint should cost one yt-dlp call, not two."""
    requested: list[str] = []

    def fake_ytdlp(args, timeout, what):
        lang = args[args.index("--sub-langs") + 1]
        requested.append(lang)
        (tmp_path / "caps.x.vtt").write_text("WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nhi\n")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(ingest, "_ytdlp", fake_ytdlp)
    ingest._fetch_captions("https://youtu.be/abc", tmp_path, "en")
    assert requested == ["en.*"], "en hint must try English first and stop there"


def test_leftover_track_from_an_earlier_attempt_is_not_mistaken_for_success(
    monkeypatch, tmp_path
):
    """Each attempt clears caps*.vtt first. Without that, a file left behind by
    a failed attempt would be re-read and reported as a fresh hit, and the
    caller would never move on to the next language."""
    (tmp_path / "caps.hi.vtt").write_text("left over from a failed attempt")

    monkeypatch.setattr(
        ingest,
        "_ytdlp",
        lambda a, t, w: subprocess.CompletedProcess(a, 1, "", "429"),
    )
    assert ingest._fetch_captions("https://youtu.be/abc", tmp_path) is None


def test_captions_none_when_nothing_on_disk(monkeypatch, tmp_path):
    monkeypatch.setattr(
        ingest,
        "_ytdlp",
        lambda a, t, w: subprocess.CompletedProcess(a, 1, "", "429"),
    )
    assert ingest._fetch_captions("https://youtu.be/abc", tmp_path) is None


def test_captions_pick_the_longest_track(monkeypatch, tmp_path):
    def fake_ytdlp(args, timeout, what):
        (tmp_path / "caps.en.vtt").write_text("short track", encoding="utf-8")
        (tmp_path / "caps.en-orig.vtt").write_text(
            "a much longer auto generated track", encoding="utf-8"
        )
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(ingest, "_ytdlp", fake_ytdlp)
    assert ingest._fetch_captions("https://youtu.be/abc", tmp_path) == (
        "a much longer auto generated track"
    )


def test_only_two_caption_languages_are_attempted():
    """Every extra language is another 429 surface against YouTube."""
    for order in ingest._SUB_LANG_ORDER.values():
        assert len(order) == 2
    assert "ur" not in "".join(ingest._SUB_LANG_ORDER["auto"])


def test_language_hint_is_validated_before_any_fetch():
    with pytest.raises(PipelineError) as e:
        ingest.ingest_url("https://youtu.be/abc", language_hint="fr")
    assert e.value.status == 400


def test_oversized_transcript_is_truncated_and_reported(monkeypatch):
    """Long reel: we cut to the analyze cap and say how much went, instead of
    letting the verdict silently rest on half the content."""
    long_text = "buy my premium course now " * 900
    monkeypatch.setattr(ingest, "_resolve_public_url", lambda u: (u, "youtu.be"))
    monkeypatch.setattr(ingest, "_SLOTS", __import__("threading").BoundedSemaphore(1))
    monkeypatch.setattr(
        ingest, "_probe", lambda u, w: {"title": "long", "duration": 90.0}
    )
    monkeypatch.setattr(ingest, "_fetch_captions", lambda u, w, h="auto": long_text)
    monkeypatch.setattr(
        ingest, "_fetch_media", lambda u, w: (_ for _ in ()).throw(AssertionError("no dl"))
    )

    out = ingest.ingest_url("https://youtu.be/abc")
    assert out["truncated"] is True
    assert out["dropped_chars"] > 0
    assert len(out["transcript"]) <= MAX_ANALYZE_CHARS
    assert out["source"] == "captions"
    assert out["title"] == "long"


def test_long_video_rejected_before_download(monkeypatch):
    monkeypatch.setattr(ingest, "_resolve_public_url", lambda u: (u, "youtu.be"))
    monkeypatch.setattr(ingest, "_SLOTS", __import__("threading").BoundedSemaphore(1))
    monkeypatch.setattr(
        ingest, "_probe", lambda u, w: {"title": "lecture", "duration": 3600.0}
    )
    monkeypatch.setattr(
        ingest, "_fetch_captions",
        lambda u, w, h="auto": (_ for _ in ()).throw(AssertionError("must not fetch")),
    )

    with pytest.raises(PipelineError) as e:
        ingest.ingest_url("https://youtu.be/abc")
    assert e.value.status == 413


def test_captions_short_circuit_the_media_path(monkeypatch, tmp_path):
    monkeypatch.setattr(ingest, "_resolve_public_url", lambda u: (u, "youtu.be"))
    monkeypatch.setattr(ingest, "_SLOTS", __import__("threading").BoundedSemaphore(1))
    monkeypatch.setattr(ingest, "_probe", lambda u, w: {"title": "t", "duration": 42.0})
    monkeypatch.setattr(ingest, "_fetch_captions", lambda u, w, h="auto": "join my premium group")
    monkeypatch.setattr(
        ingest, "_fetch_media", lambda u, w: (_ for _ in ()).throw(AssertionError("no dl"))
    )

    out = ingest.ingest_url("https://youtu.be/abc")
    assert out["source"] == "captions"
    assert out["truncated"] is False
    assert out["dropped_chars"] == 0
    assert out["duration_sec"] == 42.0


def test_missing_ytdlp_is_a_500_not_a_crash(monkeypatch, tmp_path):
    def missing(*a, **k):
        raise FileNotFoundError

    monkeypatch.setattr(ingest.subprocess, "run", missing)
    with pytest.raises(PipelineError) as e:
        ingest._ytdlp(["yt-dlp", "--version"], 5, "link")
    assert e.value.status == 500


# ------------------------------------------------------------- shared routing


def test_normalize_transcript_routes_urdu_script_to_hindi():
    from transcribe import normalize_transcript

    text, lang = normalize_transcript("پککہ منافہ تیس دن میں پیسہ دبل", "auto")
    assert lang == "hi"
    assert text == "पक्का मुनाफा तीस दिन में पैसा डबल"


def test_normalize_transcript_respects_explicit_hint():
    from transcribe import normalize_transcript

    assert normalize_transcript("plain english", "en")[1] == "en"
    assert normalize_transcript("देवनागरी", "auto")[1] == "hi"


# ------------------------------------------------------------------- HTTP wire

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_endpoint_rejects_metadata_url(client):
    """The headline SSRF case, end to end through the router."""
    res = client.post("/api/ingest-url", json={"url": "http://169.254.169.254/latest/"})
    assert res.status_code == 400
    assert "169.254" not in res.json()["detail"]


def test_endpoint_rejects_loopback(client):
    res = client.post("/api/ingest-url", json={"url": "http://127.0.0.1:8000/health"})
    assert res.status_code == 400


def test_endpoint_rejects_unsupported_platform(client):
    res = client.post("/api/ingest-url", json={"url": "https://example.com/video/1"})
    assert res.status_code == 400
    assert "not supported" in res.json()["detail"].lower()


def test_endpoint_rejects_empty_url(client):
    assert client.post("/api/ingest-url", json={"url": ""}).status_code == 422


def test_endpoint_rejects_bad_language_hint(client):
    res = client.post(
        "/api/ingest-url", json={"url": "https://youtu.be/abc", "language_hint": "de"}
    )
    assert res.status_code == 400


def test_meta_advertises_url_ingest(client):
    body = client.get("/api/meta").json()
    assert body["url_ingest"]["available"] is True
    assert set(body["url_ingest"]["sources"]) == {"captions", "media"}
