import json
from gateway.streaming import _notify_tool_calls


def test_completed_write_call_is_handed_to_callback():
    seen = []
    stats = {"names": {0: "project_write_file"},
             "args": {0: json.dumps({"path": "src/a.tsx", "content": "export function A() { return 1; }"})}}
    _notify_tool_calls(stats, lambda n, a: seen.append((n, a["path"])))
    assert seen == [("project_write_file", "src/a.tsx")]


def test_broken_arguments_are_skipped_not_raised():
    seen = []
    stats = {"names": {0: "project_write_file"}, "args": {0: '{"path": "src/a'}}
    _notify_tool_calls(stats, lambda n, a: seen.append(n))
    assert seen == []


def test_no_callback_is_a_noop():
    _notify_tool_calls({"names": {0: "x"}, "args": {0: "{}"}}, None)


def test_apply_patch_updates_known_file_once():
    from gateway.engines.symbol_index import SymbolIndex
    idx = SymbolIndex()
    idx.observe("src/a.tsx", "export function A() {\n  return 'Export';\n}\n")
    assert idx.apply_patch("src/a.tsx", "return 'Export';", "return 'CSV';") == "changed"
    assert "CSV" in idx.files()["src/a.tsx"]


def test_apply_patch_misses_unknown_or_ambiguous():
    from gateway.engines.symbol_index import SymbolIndex
    idx = SymbolIndex()
    assert idx.apply_patch("src/x.tsx", "a", "b") == "miss"
    idx.observe("src/x.tsx", "a a")
    assert idx.apply_patch("src/x.tsx", "a", "b") == "miss"
