"""Landing: provider and model dropdowns half and half; remove the benchmark card; no scrollbar.

Usage: python landing_half_row.py <bolt_root>
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


MS = "app/components/chat/ModelSelector.tsx"
BASE = "app/components/chat/BaseChat.tsx"

# Dropdowns: provider and model each take half the row, on every screen size.
edit(MS, '    <div className="flex gap-2 flex-col sm:flex-row">', '    <div className="flex gap-2 flex-row w-full">')
edit(MS, '      <div className="relative flex w-full" onKeyDown={handleProviderKeyDown} ref={providerDropdownRef}>',
     '      <div className="relative flex w-1/2 min-w-0" onKeyDown={handleProviderKeyDown} ref={providerDropdownRef}>')
edit(MS, '      <div className="relative flex w-full min-w-[70%]" onKeyDown={handleModelKeyDown} ref={modelDropdownRef}>',
     '      <div className="relative flex w-1/2 min-w-0" onKeyDown={handleModelKeyDown} ref={modelDropdownRef}>')

# Remove the benchmark card.
p = root / BASE
s = p.read_text(encoding="utf-8")
start = s.index('                    <div className="mt-4 rounded-xl border border-bolt-elements-borderColor p-4 text-center">')
end = s.index("                    </div>\n", s.index("Veylqora: 100%", start)) + len("                    </div>\n")
s = s[:start] + s[end:]
p.write_text(s, encoding="utf-8")
print("removed benchmark card")
