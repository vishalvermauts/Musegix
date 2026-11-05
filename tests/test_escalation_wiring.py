from gateway.engines.repair import escalate_after_failures


def test_two_failures_escalate_trivial_to_moderate():
    assert escalate_after_failures("TRIVIAL", [False, True, True]) == "MODERATE"


def test_one_failure_does_not_escalate():
    assert escalate_after_failures("TRIVIAL", [False, True]) == "TRIVIAL"


def test_success_resets_streak():
    assert escalate_after_failures("TRIVIAL", [True, True, False]) == "TRIVIAL"


def test_hard_is_the_ceiling():
    assert escalate_after_failures("HARD", [True, True]) == "HARD"
