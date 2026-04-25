from mercury import copilot_models as cm


def test_zero_premium_set_matches_table():
    ids = {m.model_id for m in cm.ZERO_PREMIUM_MODELS}
    assert ids == {"gpt-5-mini", "gpt-4o", "gpt-4.1"}
    for m in cm.ZERO_PREMIUM_MODELS:
        assert m.multiplier == 0.0
        assert m.provider == "copilot"


def test_default_fulltime_is_gpt5_mini():
    assert cm.DEFAULT_FULLTIME_BRAIN.model_id == "gpt-5-mini"
    assert cm.DEFAULT_FULLTIME_BRAIN.multiplier == 0.0


def test_default_vision_supports_vision():
    assert cm.DEFAULT_VISION_BRAIN.supports_vision is True
    assert cm.DEFAULT_VISION_BRAIN.multiplier == 0.0


def test_parttime_is_gemma_via_ollama():
    assert cm.DEFAULT_PARTTIME_BRAIN.provider == "ollama"
    assert cm.DEFAULT_PARTTIME_BRAIN.model_id == "gemma4:e4b"


def test_is_zero_premium():
    assert cm.is_zero_premium("gpt-5-mini") is True
    assert cm.is_zero_premium("gpt-4o") is True
    assert cm.is_zero_premium("gpt-4.1") is True
    assert cm.is_zero_premium("claude-sonnet-4-6") is False
    assert cm.is_zero_premium("gemma4:e4b") is False  # local, not copilot
    assert cm.is_zero_premium("nonexistent-model") is False


def test_escalations_are_one_x_or_paid():
    for m in cm.ESCALATION_MODELS:
        assert m.multiplier >= 1.0
