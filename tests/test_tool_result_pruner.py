from gateway.engines.tool_result_pruner import prune_tool_results

BIG = "output line\n" * 200


def test_old_success_results_pruned_recent_kept():
    msgs = [{"role": "tool", "content": BIG} for _ in range(8)]
    out, before, after = prune_tool_results(msgs, keep_last=6)
    assert after < before
    assert "PolyFabric: old tool output pruned" in out[0]["content"]
    assert out[-1]["content"] == BIG and out[-6]["content"] == BIG


def test_failures_are_never_pruned():
    fail = '{"isError":true,"problems":["Syntax check failed"]}' + BIG
    msgs = [{"role": "tool", "content": fail}] + [{"role": "tool", "content": BIG} for _ in range(7)]
    out, _, _ = prune_tool_results(msgs, keep_last=6)
    assert out[0]["content"] == fail


def test_short_results_and_non_tool_messages_untouched():
    msgs = [{"role": "user", "content": BIG}, {"role": "tool", "content": "ok"}] + [{"role": "tool", "content": BIG}] * 6
    out, _, _ = prune_tool_results(msgs, keep_last=6)
    assert out[0]["content"] == BIG and out[1]["content"] == "ok"


def test_input_not_mutated():
    msgs = [{"role": "tool", "content": BIG} for _ in range(8)]
    prune_tool_results(msgs)
    assert all(m["content"] == BIG for m in msgs)
