import json

from gateway.engines.polyfabric_pruner import count_tokens
from gateway.engines.symbol_index import (
    SYMBOL_MAP_HEADER,
    index_for_chat,
    inject_symbol_map,
    reset_indexes,
)

TSX = """import React from 'react';

export function SettingsPage() {
  return <div />;
}

const ApiKeysCard = () => {
  return <div />;
};
"""

PY = """def load(path):
    return open(path).read()


class Store:
    def get(self, key):
        return key
"""


def _write(call_id, path, content):
    return [
        {"role": "assistant", "content": None, "tool_calls": [{
            "id": call_id, "type": "function",
            "function": {"name": "project_write_file",
                         "arguments": json.dumps({"path": path, "content": content})}}]},
        {"role": "tool", "tool_call_id": call_id, "content": '{"ok": true}'},
    ]


def _read(call_id, path, content):
    return [
        {"role": "assistant", "content": None, "tool_calls": [{
            "id": call_id, "type": "function",
            "function": {"name": "project_read_file", "arguments": json.dumps({"path": path})}}]},
        {"role": "tool", "tool_call_id": call_id,
         "content": json.dumps({"path": path, "content": content, "revision": "r1"})},
    ]


def setup_function():
    reset_indexes()


def test_build_extracts_ranges_for_functions_components_and_python():
    idx = index_for_chat("chat-build")
    changed, new = idx.ingest_messages(
        _write("w1", "src/pages/Settings.tsx", TSX) + _write("w2", "app/util.py", PY)
    )
    assert changed == []
    assert sorted(new) == ["app/util.py", "src/pages/Settings.tsx"]
    cmap = idx.compact_map()
    assert "src/pages/Settings.tsx: SettingsPage L3-5, ApiKeysCard L7-9" in cmap
    assert "app/util.py: load L1-2, Store L5-7" in cmap  # methods are indexed but kept out of the map
    store_methods = [s for s in idx.symbols("app/util.py") if s.kind == "method"]
    assert [(s.name, s.start, s.end) for s in store_methods] == [("Store.get", 6, 7)]
    assert [s.name for s in idx.symbols("src/pages/Settings.tsx") if s.exported] == ["SettingsPage"]


def test_map_stays_under_500_tokens_for_many_files():
    idx = index_for_chat("chat-big")
    msgs = []
    for i in range(300):
        body = "\n".join(
            f"export function handler{i}_{j}(a, b) {{\n  return a + b;\n}}" for j in range(6)
        )
        msgs += _write(f"w{i}", f"src/features/module_{i:03d}/index.ts", body)
    idx.ingest_messages(msgs)
    cmap = idx.compact_map(max_tokens=500)
    assert cmap
    assert count_tokens(cmap) <= 500
    assert len(cmap.splitlines()) < 300  # the budget cut the list short


def test_per_chat_isolation():
    a = index_for_chat("chat-a")
    b = index_for_chat("chat-b")
    a.ingest_messages(_write("w1", "src/a.ts", "export function onlyInA() {\n  return 1;\n}\n"))
    assert "onlyInA" in a.compact_map()
    assert b.compact_map() == ""
    assert index_for_chat("chat-a") is a
    assert index_for_chat("chat-b") is b


def test_changed_file_updates_hash_and_map():
    idx = index_for_chat("chat-change")
    idx.ingest_messages(_write("w1", "src/x.ts", "export function alpha() {\n  return 1;\n}\n"))
    before = idx.digest("src/x.ts")

    # Replaying the same history changes nothing.
    same = _write("w1", "src/x.ts", "export function alpha() {\n  return 1;\n}\n")
    assert idx.ingest_messages(same) == ([], [])
    assert idx.digest("src/x.ts") == before

    changed_msgs = _write(
        "w2", "src/x.ts",
        "export function alpha() {\n  return 1;\n}\n\nexport function beta() {\n  return 2;\n}\n",
    )
    changed, new = idx.ingest_messages(changed_msgs)
    assert changed == ["src/x.ts"] and new == []
    assert idx.digest("src/x.ts") != before
    assert "beta L5-7" in idx.compact_map()


def test_ingest_uses_last_state_and_skips_pruned_or_failed_reads():
    idx = index_for_chat("chat-state")
    msgs = (
        _write("w1", "src/y.ts", "export const v1 = () => 1;\n")
        + _write("w2", "src/y.ts", "export const v2 = () => 2;\n")
        + _read("r1", "src/y.ts", "export const v2 = () => 2;\n")
    )
    idx.ingest_messages(msgs)
    assert [s.name for s in idx.symbols("src/y.ts")] == ["v2"]

    pruned = [
        {"role": "assistant", "content": None, "tool_calls": [{
            "id": "r9", "type": "function",
            "function": {"name": "project_read_file", "arguments": json.dumps({"path": "src/y.ts"})}}]},
        {"role": "tool", "tool_call_id": "r9",
         "content": "export const v2 = ...\n[PolyFabric: old tool output pruned, 900 chars]"},
    ]
    assert idx.ingest_messages(pruned) == ([], [])
    assert [s.name for s in idx.symbols("src/y.ts")] == ["v2"]


def test_inject_symbol_map_only_when_non_empty():
    msgs = [{"role": "system", "content": "You are bolt."}, {"role": "user", "content": "hi"}]
    assert inject_symbol_map(msgs, "") is msgs
    out = inject_symbol_map(msgs, "src/a.ts: f L1-3")
    assert out[0]["content"].startswith("You are bolt.")
    assert SYMBOL_MAP_HEADER in out[0]["content"]
    assert out[0]["content"].endswith("src/a.ts: f L1-3")
    assert msgs[0]["content"] == "You are bolt."  # input not mutated
    no_sys = inject_symbol_map([{"role": "user", "content": "hi"}], "src/a.ts: f L1-3")
    assert no_sys[0]["role"] == "system"
