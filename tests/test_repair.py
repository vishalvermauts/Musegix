import json

from gateway.engines.polyfabric_pruner import PolyFabricPruner
from gateway.engines.repair import (
    escalate_after_failures,
    impact_banner,
    referenced_mutations,
    repair_target_file,
    tool_failure_flags,
)
from gateway.engines.veylqora_guard import GuardReport, MutatedSymbol


def _call(call_id, name, args):
    return [{"role": "assistant", "content": None, "tool_calls": [{
        "id": call_id, "type": "function",
        "function": {"name": name, "arguments": json.dumps(args)}}]}]


def _tool(call_id, content):
    return {"role": "tool", "tool_call_id": call_id, "content": content}


FAIL = '{"exitCode": 2, "output": "src/b.tsx:3:5 - error TS2322: Type string is not assignable"}'
OK = '{"exitCode": 0, "output": "build ok"}'


def test_repair_target_from_newest_failure_only():
    msgs = _call("c1", "project_run_command", {"command": "tsc"}) + [_tool("c1", FAIL)]
    assert repair_target_file(msgs) == "src/b.tsx"

    msgs_fixed = msgs + _call("c2", "project_run_command", {"command": "tsc"}) + [_tool("c2", OK)]
    assert repair_target_file(msgs_fixed) is None

    assert repair_target_file([]) is None
    assert repair_target_file([{"role": "user", "content": "hi"}]) is None


def test_repair_target_normalises_project_prefix():
    msgs = [_tool("c1", '{"exitCode": 1, "output": "/home/project/app/page.py:12 NameError"}')]
    assert repair_target_file(msgs) == "app/page.py"


def test_tool_failure_flags_order():
    msgs = [_tool("a", OK), _tool("b", FAIL), _tool("c", FAIL)]
    assert tool_failure_flags(msgs) == [False, True, True]


def test_escalate_after_two_consecutive_failures():
    assert escalate_after_failures("MODERATE", [False, True, True]) == "HARD"
    assert escalate_after_failures("TRIVIAL", [True, True]) == "MODERATE"
    assert escalate_after_failures("TRIVIAL", [True, True, True, True]) == "MODERATE"
    assert escalate_after_failures("HARD", [True, True]) == "HARD"
    assert escalate_after_failures("MODERATE", [True]) == "MODERATE"
    assert escalate_after_failures("MODERATE", [True, False, True]) == "MODERATE"
    assert escalate_after_failures("MODERATE", []) == "MODERATE"
    assert escalate_after_failures("UNKNOWN", [True, True]) == "UNKNOWN"


def test_repair_keeps_failing_file_whole_and_stubs_the_rest():
    a_body = "export function helperA() {\n  return 'A_ONLY_LINE_XYZ';\n}\n"
    b_body = "export function helperB() {\n  return 'B_FULL_LINE_QRS';\n}\n"
    context = (
        '<boltArtifact id="x" title="t">\n'
        f'<boltAction type="file" filePath="src/a.ts">\n{a_body}</boltAction>\n'
        f'<boltAction type="file" filePath="src/b.tsx">\n{b_body}</boltAction>\n'
        "</boltArtifact>"
    )
    pruner = PolyFabricPruner()
    kept = pruner.prune_context(context_text=context, user_prompt="fix the build", target_files=["src/b.tsx"])
    assert "B_FULL_LINE_QRS" in kept.pruned_text
    assert "A_ONLY_LINE_XYZ" not in kept.pruned_text
    assert "src/a.ts" in kept.pruned_files


class FakeGuard:
    """Stands in for VeylqoraGuard: reports one changed export between two requests."""

    def __init__(self, mutated):
        self.mutated = mutated
        self.calls = []

    def inspect_turn(self, session_id, files, advance_turn=False):
        self.calls.append((session_id, dict(files), advance_turn))
        return GuardReport(status="SUSPECTED_STALE", stale_count=len(self.mutated), mutated_symbols=self.mutated)


def test_veylqora_reports_changed_exports_used_elsewhere():
    guard = FakeGuard([
        MutatedSymbol("src/lib/format.ts", "formatPrice", "function", "old", "new"),
        MutatedSymbol("src/lib/format.ts", "$file", "file", "old", "new"),
    ])
    files = {
        "src/lib/format.ts": "export function formatPrice(n) { return n; }",
        "src/Cart.tsx": "import { formatPrice } from './lib/format';\nformatPrice(3);",
        "src/Other.tsx": "const unrelated = 1;",
    }
    rep = guard.inspect_turn("chat-1", files, advance_turn=True)
    impact = referenced_mutations(rep.mutated_symbols, files)
    assert impact == {"formatPrice": ["src/Cart.tsx"]}
    banner = impact_banner(impact)
    assert "formatPrice" in banner and "src/Cart.tsx" in banner
    assert impact_banner({}) is None


def test_veylqora_impact_ignores_the_changed_file_itself():
    files = {"src/a.ts": "export function solo() {}"}
    impact = referenced_mutations(
        [MutatedSymbol("src/a.ts", "solo", "function", "1", "2")], files
    )
    assert impact == {}
