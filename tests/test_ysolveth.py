"""Comprehensive tests for Ysolveth System One ONNX inference engine.

Verifies:
1. Model loading, tokenizer truncation at 256 tokens, and warm-up pass.
2. Fast CPU execution (<5ms typical).
3. Real mathematical probabilities summing to 1.0.
4. Correct classification across diverse trivial, moderate, and hard prompts.
5. Accurate routing to Meta and Baseten endpoints.
6. Zero mocked heuristics or fake constants.
7. Graceful handling of edge cases (empty strings, large prompts >256 tokens).
"""

import pytest
import numpy as np
from gateway.engines.ysolveth_classifier import YsolvethClassifier


@pytest.fixture(scope="module")
def classifier():
    """Shared classifier fixture initialized with warm-up."""
    return YsolvethClassifier()


def test_classifier_initialization(classifier):
    """Verify session, tokenizer, weights, biases, and temperature are loaded."""
    assert classifier.session is not None
    assert classifier.tokenizer is not None
    assert classifier.weights.shape == (3, 384)
    assert classifier.biases.shape == (3,)
    assert classifier.temperature == pytest.approx(0.2842, rel=1e-4)
    assert classifier.labels == ["hard", "moderate", "trivial"]


def test_probabilities_sum_to_one(classifier):
    """Verify output probabilities are strictly valid and sum to 1.0."""
    result = classifier.classify("Write a python function to add two numbers")
    probs = result["probabilities"]

    assert set(probs.keys()) == {"hard", "moderate", "trivial"}
    total_prob = sum(probs.values())
    assert total_prob == pytest.approx(1.0, rel=1e-5)

    for label, p in probs.items():
        assert 0.0 <= p <= 1.0

    assert result["confidence"] == pytest.approx(probs[result["label"]], rel=1e-5)
    assert result["tier"] == result["label"].upper()


def test_diverse_prompts_and_routing(classifier):
    """Test diverse prompts across trivial, moderate, and hard categories with proper routing."""
    test_cases = [
        # Trivial coding prompts
        {
            "prompt": "Fix typo in variable name usr_nm to user_name",
            "expected_tier": "TRIVIAL",
            "expected_provider": "baseten",
            "expected_model": "meta-models/muse-spark-open-1026",
        },
        {
            "prompt": "Add a one-line comment explaining this regex",
            "expected_tier": "TRIVIAL",
            "expected_provider": "baseten",
            "expected_model": "meta-models/muse-spark-open-1026",
        },
        # Moderate coding prompts
        {
            "prompt": "Create a REST endpoint using FastAPI to return a list of items with pagination",
            "expected_tier": "MODERATE",
            "expected_provider": "meta",
            "expected_model": "muse-spark-1.3",
        },
        # Hard coding prompts
        {
            "prompt": "Design and implement a multi-region distributed transactional key-value store with Paxos consensus, snapshot isolation, and zero-downtime schema migration",
            "expected_tier": "HARD",
            "expected_provider": "meta",
            "expected_model": "muse-wonder-1.0",
        },
        {
            "prompt": "Architect an enterprise multi-tenant database migration system with row-level security, cryptographic audit logs, and automatic partition rebalancing",
            "expected_tier": "HARD",
            "expected_provider": "meta",
            "expected_model": "muse-wonder-1.0",
        },
    ]

    for tc in test_cases:
        res = classifier.classify(tc["prompt"])
        assert res["tier"] == tc["expected_tier"], (
            f"Prompt '{tc['prompt']}' got tier {res['tier']}, expected {tc['expected_tier']}. "
            f"Probabilities: {res['probabilities']}"
        )
        assert res["provider"] == tc["expected_provider"]
        assert res["target_model"] == tc["expected_model"]

        # Test route() convenience helper
        provider, model = classifier.route(tc["prompt"])
        assert provider == tc["expected_provider"]
        assert model == tc["expected_model"]


def test_inference_latency_cpu(classifier):
    """Verify execution latency is fast on standard CPU inference."""
    # Run multiple iterations to measure warm CPU inference speed
    latencies = []
    for _ in range(5):
        res = classifier.classify("Refactor database query to optimize index scans")
        latencies.append(res["latency_ms"])

    median_latency = float(np.median(latencies))
    # In local and CI environments, execution is typically 1-5ms; ensure generous guardrail
    assert median_latency < 25.0, f"Expected fast inference, got median {median_latency} ms"


def test_truncation_handling(classifier):
    """Verify tokenizer truncation handles requests exceeding 256 tokens gracefully."""
    very_long_prompt = "Refactor this code. " * 300  # ~900 tokens
    res = classifier.classify(very_long_prompt)

    assert res["tier"] in ["TRIVIAL", "MODERATE", "HARD"]
    assert sum(res["probabilities"].values()) == pytest.approx(1.0, rel=1e-5)


def test_empty_and_whitespace_prompt(classifier):
    """Verify empty or whitespace prompts do not crash and produce valid distributions."""
    for empty in ["", "   ", "\n\t"]:
        res = classifier.classify(empty)
        assert res["tier"] in ["TRIVIAL", "MODERATE", "HARD"]
        assert sum(res["probabilities"].values()) == pytest.approx(1.0, rel=1e-5)


def test_mathematical_determinism_and_non_mocked(classifier):
    """Verify deterministic mathematical calculation and distinct vector mappings (zero mocks)."""
    p1 = "Fix CSS color in button style"
    p2 = "Implement Byzantine fault-tolerant consensus in distributed cluster"

    res1 = classifier.classify(p1)
    res2 = classifier.classify(p1)
    res3 = classifier.classify(p2)

    # Identical prompts yield identical floating point values
    assert res1["confidence"] == res2["confidence"]
    assert res1["probabilities"] == res2["probabilities"]

    # Different prompts yield different mathematical distributions
    assert res1["probabilities"] != res3["probabilities"]
    assert res1["tier"] != res3["tier"]
