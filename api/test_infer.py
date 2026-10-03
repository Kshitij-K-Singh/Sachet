"""Shadow-model wiring tests. Skipped when the optional ML stack
(torch/transformers) or the LoRA adapter is absent -- the slim runtime
image intentionally ships without them and second_opinion() returns None.
"""

import pytest

from fastapi.testclient import TestClient

from main import app
from ml.infer import second_opinion

PROMO = "Guaranteed returns! Double your money in 30 days, 100% safe, no risk. Join our premium Telegram group now!"

requires_model = pytest.mark.skipif(
    second_opinion(PROMO) is None,
    reason="shadow model unavailable (SACHET_MODEL=off, no torch, or no adapter)",
)


@requires_model
def test_second_opinion_shape():
    op = second_opinion(PROMO)
    assert op is not None
    assert op["label"] in ("education", "mixed", "promotion")
    assert 0.0 <= op["confidence"] <= 1.0


def test_analyze_runs_without_model_opinion():
    """The rubric verdict must not depend on the optional shadow model."""
    client = TestClient(app)
    res = client.post("/api/analyze", json={"text": PROMO})
    assert res.status_code == 200
    body = res.json()
    assert body["classification"] == "promotion"
    model = body.get("model")
    if model is not None:
        assert model["label"] in ("education", "mixed", "promotion")
