"""Landing cards: say what each engine saves (tokens, dollar spend, on-device routing).

Usage: python landing_savings_copy.py <bolt_root>
"""
import pathlib
import sys

root = pathlib.Path(sys.argv[1])

REPLACEMENTS = [
    ("title: 'Smart routing. Every turn.'", "title: 'On-device System 1 routing.'"),
    (
        "body: 'A trained local model assesses each request, routing simple edits to fast models and complex work to stronger reasoning.'",
        "body: 'A trained model runs on your CPU in milliseconds and sends simple edits to cheaper models, so dollar spend drops. Complex work still goes to the stronger model.'",
    ),
    ("title: 'Focused context. Less waste.'", "title: 'Fewer tokens. Lower spend.'"),
    (
        "body: 'Keeps relevant project context in focus and trims older file reads and command logs before they reach the model.'",
        "body: 'Trims old file reads and command logs and sends only the files a request needs, so each step sends fewer tokens and costs less.'",
    ),
    ("statLabel: 'less old tool output sent'", "statLabel: 'fewer tokens sent on old tool output'"),
]

for rel in ["app/components/chat/BaseChat.tsx"]:
    for base in ["external/bolt.diy", "vendor/bolt.diy"]:
        p = root / base / rel
        s = p.read_text(encoding="utf-8")
        for old, new in REPLACEMENTS:
            assert s.count(old) == 1, (base, old[:60], s.count(old))
            s = s.replace(old, new)
        p.write_text(s, encoding="utf-8")
        print("updated", base, rel)
