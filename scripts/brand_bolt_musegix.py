"""Apply Musegix branding to a bolt.diy tree: wordmark, dark theme colours, title, visible bolt.diy text.

Usage: python scripts/brand_bolt_musegix.py <bolt_root>
"""
import pathlib
import sys

root = pathlib.Path(sys.argv[1])


def edit(rel, old, new, count=1):
    p = root / rel
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == count, (rel, s.count(old), old[:60])
    p.write_text(s.replace(old, new), encoding="utf-8")
    print("edited", rel)


# 1. Header: replace bolt logo images with a Musegix wordmark.
edit(
    "app/components/header/Header.tsx",
    '          <img src="/logo-light-styled.png" alt="logo" className="w-[90px] inline-block dark:hidden" />\n'
    '          <img src="/logo-dark-styled.png" alt="logo" className="w-[90px] inline-block hidden dark:block" />',
    '          <span className="text-xl font-bold tracking-wide text-white">Musegix</span>',
)

# 2. Dark theme colours from the brief: black background, #111 panels, #4d8fe0 accent.
edit(
    "app/styles/variables.scss",
    "  --bolt-elements-bg-depth-1: theme('colors.gray.950');\n"
    "  --bolt-elements-bg-depth-2: theme('colors.gray.900');\n"
    "  --bolt-elements-bg-depth-3: theme('colors.gray.800');",
    "  --bolt-elements-bg-depth-1: #000000;\n"
    "  --bolt-elements-bg-depth-2: #111111;\n"
    "  --bolt-elements-bg-depth-3: #1a1a1a;",
    count=1,
)
edit(
    "app/styles/variables.scss",
    "  --bolt-elements-borderColorActive: theme('colors.accent.500');\n\n  --bolt-elements-bg-depth-1: #000000;",
    "  --bolt-elements-borderColorActive: #4d8fe0;\n\n  --bolt-elements-bg-depth-1: #000000;",
)
edit(
    "app/styles/variables.scss",
    "  --bolt-elements-button-primary-text: theme('colors.accent.500');",
    "  --bolt-elements-button-primary-text: #4d8fe0;",
    count=2,
)

# 3. Visible bolt.diy text in the bug-report panel (the upstream link is kept for attribution).
edit("app/components/header/ReportBugPanel.tsx", "Help us improve bolt.diy", "Help us improve Musegix")
edit("app/components/header/ReportBugPanel.tsx", "bolt.diy team.", "Musegix team.")
