"""Landing: remove suggestion pills, shorter composer (-20%), blue palette from the brief instead of purple.

Usage: python landing_colors.py <bolt_root>
"""
import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1])
BASE = "app/components/chat/BaseChat.tsx"
MS = "app/components/chat/ModelSelector.tsx"
UNO = "uno.config.ts"


def read(rel):
    return (root / rel).read_text(encoding="utf-8")


def write(rel, s):
    (root / rel).write_text(s, encoding="utf-8")


# 1. Remove the suggestion pills block.
s = read(BASE)
start = s.index("                {!chatStarted && (\n                  <div className=\"flex flex-wrap justify-center gap-2\">")
end = s.index("                )}\n", start) + len("                )}\n")
s = s[:start] + s[end:]

# 2. Composer 20% shorter: 180 -> 144.
assert s.count("const TEXTAREA_MIN_HEIGHT = 180;") == 1
s = s.replace("const TEXTAREA_MIN_HEIGHT = 180;", "const TEXTAREA_MIN_HEIGHT = 144;")
write(BASE, s)
print("edited", BASE)

# 3. Accent palette: the brief's blue (#4d8fe0) replaces bolt's purple.
u = read(UNO)
old_block = re.search(r"  accent: \{\n(.*?)\n  \},", u, re.S).group(0)
blue = (
    "  accent: {\n"
    "    50: '#EEF5FD',\n"
    "    100: '#DCEAFB',\n"
    "    200: '#B9D5F7',\n"
    "    300: '#8DBBF2',\n"
    "    400: '#6AA5EC',\n"
    "    500: '#4d8fe0',\n"
    "    600: '#3B78C9',\n"
    "    700: '#2E62A8',\n"
    "    800: '#254E87',\n"
    "    900: '#1D3D6B',\n"
    "    950: '#13284A',\n"
    "  },"
)
write(UNO, u.replace(old_block, blue, 1))
print("edited", UNO)

# 4. Purple Tailwind classes in the model selector become blue.
m = read(MS)
m2, n = re.subn(r"\bpurple-(\d{2,3})", r"blue-\1", m)
write(MS, m2)
print("edited", MS, "purple classes replaced:", n)
