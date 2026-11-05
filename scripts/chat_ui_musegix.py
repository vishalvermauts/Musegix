"""Main chat UI: Musegix wording and blue instead of purple in the chat, workbench, header and sidebar.

Usage: python chat_ui_musegix.py <bolt_root>
"""
import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1])
TEXT = [
    ("Bolt Terminal", "Terminal"),
    ("Bolt Restored your chat from a snapshot.", "Musegix restored your chat from a snapshot."),
]
DIRS = ["app/components/chat", "app/components/workbench", "app/components/header", "app/components/sidebar"]

for base in ["external/bolt.diy", "vendor/bolt.diy"]:
    changed = 0
    purple_total = 0
    for d in DIRS:
        for p in (root / base / d).rglob("*.tsx"):
            s = p.read_text(encoding="utf-8")
            orig = s
            for old, new in TEXT:
                s = s.replace(old, new)
            s, n = re.subn(r"\bpurple-(\d{2,3})", r"blue-\1", s)
            purple_total += n
            if s != orig:
                p.write_text(s, encoding="utf-8")
                changed += 1
    print(base, "files changed:", changed, "purple classes -> blue:", purple_total)
