"""Musegix landing v3: chat box above, hero cards below, 'Meta Model' label, cleaner font stack.

Usage: python scripts/landing_hero.py <bolt_root>
"""
import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1])


def edit(rel, old, new, count=1):
    p = root / rel
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == count, (rel, s.count(old), old[:70])
    p.write_text(s.replace(old, new), encoding="utf-8")
    print("edited", rel)


base = "app/components/chat/BaseChat.tsx"
p = root / base
s = p.read_text(encoding="utf-8")

# 1. Remove the card grid and stats line from above the chat box.
start = s.index('                <div className="grid gap-4 sm:grid-cols-3 text-left mt-6">')
end = s.index('                </p>\n', s.index('three engines')) + len('                </p>\n')
s = s[:start] + s[end:]

# 2. Hero cards below the chat box.
hero = '''                {!chatStarted && (
                  <div className="grid gap-5 md:grid-cols-3 text-left w-full max-w-5xl mx-auto mt-10 px-4">
                    {[
                      { name: 'Ysolveth', title: 'Smart routing', stat: '≈5 ms', statLabel: 'CPU routing time per prompt',
                        body: 'Every prompt is classified before any model call. Simple edits go to a cheaper model; harder work goes to a stronger one.' },
                      { name: 'PolyFabric', title: 'Context trimming', stat: '≈95%', statLabel: 'less old tool output sent',
                        body: 'Earlier file reads and command logs are trimmed on every step, and project files are reduced to the ones a request needs.' },
                      { name: 'Veylqora', title: 'Impact checks', stat: '100%', statLabel: 'mutated symbols flagged in benchmark',
                        body: 'Every function, class and component is fingerprinted. When an export changes, Musegix lists the files that still use it.' },
                    ].map((c) => (
                      <div
                        key={c.name}
                        className="rounded-2xl border border-bolt-elements-borderColor bg-gradient-to-b from-bolt-elements-background-depth-2 to-bolt-elements-background-depth-1 p-7 shadow-sm"
                      >
                        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-bolt-elements-textTertiary">{c.name}</p>
                        <h3 className="mt-2 text-2xl font-bold text-bolt-elements-textPrimary">{c.title}</h3>
                        <p className="mt-4 text-4xl font-extrabold text-white">{c.stat}</p>
                        <p className="text-sm text-bolt-elements-textTertiary">{c.statLabel}</p>
                        <p className="mt-5 text-base leading-relaxed text-bolt-elements-textSecondary">{c.body}</p>
                      </div>
                    ))}
                  </div>
                )}
'''
anchor = '              <div className="flex flex-col gap-5">\n'
assert s.count(anchor) == 1, s.count(anchor)
s = s.replace(anchor, anchor + hero, 1)

# 3. Taller chat box.
s = s.replace("const TEXTAREA_MIN_HEIGHT = 120;", "const TEXTAREA_MIN_HEIGHT = 180;", 1)
p.write_text(s, encoding="utf-8")
print("edited", base)

# 4. Show 'Meta Model' for the OpenAILike provider (internal id unchanged).
ms = "app/components/chat/ModelSelector.tsx"
edit(ms, "{provider?.name || 'Select provider'}", "{displayProviderName(provider?.name) || 'Select provider'}")
edit(ms, "__html: (providerOption as any).highlightedName || providerOption.name,",
     "__html: (providerOption as any).highlightedName || displayProviderName(providerOption.name),")
m = (root / ms).read_text(encoding="utf-8")
helper = "const displayProviderName = (name?: string) => (name === 'OpenAILike' ? 'Meta Model' : name);\n"
first_import_end = m.index("\n\n", m.index("import "))
m = m[:first_import_end] + "\n\n" + helper + m[first_import_end + 2:]
(root / ms).write_text(m, encoding="utf-8")
print("added displayProviderName helper")

# 5. Font: a clean system stack instead of the unloaded Inter-only default.
edit(
    "app/styles/index.scss",
    "html,\nbody {\n  height: 100%;\n  width: 100%;\n  background-color: var(--bolt-elements-bg-depth-1);\n}",
    "html,\nbody {\n  height: 100%;\n  width: 100%;\n  background-color: var(--bolt-elements-bg-depth-1);\n  font-family: 'Segoe UI', Inter, system-ui, -apple-system, 'Helvetica Neue', Arial, sans-serif;\n  -webkit-font-smoothing: antialiased;\n}",
)
