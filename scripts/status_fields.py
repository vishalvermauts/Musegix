"""Send tool-output savings and Veylqora impact to the status block, so every card has its values.

Usage: python status_fields.py <gateway_root>
"""
import pathlib
import sys

root = pathlib.Path(sys.argv[1])


def edit(rel, old, new, count=1):
    p = root / rel
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == count, (rel, s.count(old), old[:70])
    p.write_text(s.replace(old, new), encoding="utf-8")
    print("edited", rel)


R = "gateway/routes.py"
S = "gateway/streaming.py"

# routes: keep the tool-output numbers and the impact map.
edit(R, "    veylqora_note = None\n", "    veylqora_note = None\n    tool_raw = None\n    tool_kept = None\n    impact_map = {}\n")
edit(R, "            messages, tool_before, tool_after = prune_tool_results(messages)\n",
     "            messages, tool_before, tool_after = prune_tool_results(messages)\n            tool_raw, tool_kept = (tool_before or None), (tool_after or None)\n")
edit(R, "                veylqora_note = impact_banner(\n                    referenced_mutations(getattr(rep, \"mutated_symbols\", None) or [], extracted_files)\n                )\n",
     "                impact_map = referenced_mutations(getattr(rep, \"mutated_symbols\", None) or [], extracted_files)\n                veylqora_note = impact_banner(impact_map)\n")
edit(R, "            stale_memories=stale_memories,\n        )\n        # bolt.diy attaches",
     "            stale_memories=stale_memories,\n            tool_raw=tool_raw,\n            tool_kept=tool_kept,\n            impact=[{\"symbol\": k, \"files\": v[:3]} for k, v in list(impact_map.items())[:5]],\n        )\n        # bolt.diy attaches")

# streaming: add the fields to the status block.
edit(S, "    stale_memories: Optional[int] = None,\n) -> str:",
     "    stale_memories: Optional[int] = None,\n    tool_raw: Optional[int] = None,\n    tool_kept: Optional[int] = None,\n    impact: Optional[list] = None,\n) -> str:")
edit(S, "        \"staleMemories\": stale_memories,\n    }",
     "        \"staleMemories\": stale_memories,\n        \"toolRaw\": tool_raw,\n        \"toolKept\": tool_kept,\n        \"toolPrunedPct\": round(((tool_raw - tool_kept) / tool_raw) * 100, 1) if tool_raw and tool_kept is not None and tool_raw > 0 else None,\n        \"impact\": impact or [],\n    }")
