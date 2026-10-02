"""Shadow-model wiring tests. Loads the LoRA adapter once (~15s)."""

from fastapi.testclient import TestClient

from main import app
from ml.infer import second_opinion

PROMO = "Guaranteed returns! Double your money in 30 days, 100% safe, no risk. Join our premium Telegram group now!"


def test_second_opinion_shape():
    op = second_opinion(PROMO)
    assert op is not None
    assert op["label"] in ("education", "mixed", "promotion")
    assert 0.0 <= op["confidence"] <= 1.0


def test_analyze_includes_model_opinion():
    client = TestClient(app)
    res = client.post("/api/analyze", json={"text": PROMO})
    assert res.status_code == 200
    body = res.json()
    assert body["model"] is not None
    assert body["model"]["label"] in ("education", "mixed", "promotion")
    assert body["classification"] == "promotion"
