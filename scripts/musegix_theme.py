"""Add a 'Musegix' dark palette (black / #111 / #4d8fe0), make it the default dark theme,
and list it first under Dark Themes in Preferences.

Usage: python musegix_theme.py <bolt_root>
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


# 1. Palette entry, first in the dark list.
edit("app/types/theme.ts",
     "  { id: 'dark-aurora', name: 'Aurora', mode: 'dark', colors: ['#111827', '#312e81', '#a78bfa'] },",
     "  { id: 'dark-musegix', name: 'Musegix', mode: 'dark', colors: ['#000000', '#111111', '#4d8fe0'] },\n"
     "  { id: 'dark-aurora', name: 'Aurora', mode: 'dark', colors: ['#111827', '#312e81', '#a78bfa'] },")

# 2. Make it the default dark theme (toggle and first visit).
edit("app/lib/stores/theme.ts", "        ? 'dark-dracula'", "        ? 'dark-musegix'", count=1)
edit("app/lib/stores/theme.ts", "  root?.setAttribute('data-color-theme', newTheme === 'dark' ? 'dark-dracula' : newTheme);",
     "  root?.setAttribute('data-color-theme', newTheme === 'dark' ? 'dark-musegix' : newTheme);")

# 3. Palette tokens.
css = root / "app/styles/variables.scss"
s = css.read_text(encoding="utf-8")
block = """
:root[data-color-theme='dark-musegix'] {
  --bolt-elements-bg-depth-1: #000000;
  --bolt-elements-bg-depth-2: #111111;
  --bolt-elements-bg-depth-3: #1a1a1a;
  --bolt-elements-bg-depth-4: rgba(255, 255, 255, 0.05);
  --bolt-elements-borderColor: rgba(255, 255, 255, 0.1);
  --bolt-elements-borderColorActive: #4d8fe0;
  --bolt-elements-textPrimary: #ffffff;
  --bolt-elements-textSecondary: #a3a3a3;
  --bolt-elements-textTertiary: #737373;
  --bolt-elements-button-primary-text: #4d8fe0;
}
"""
css.write_text(s + block, encoding="utf-8")
print("appended palette to variables.scss")
