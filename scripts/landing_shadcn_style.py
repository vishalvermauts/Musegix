"""Musegix landing v4: wider chat box, centred shadcn-style hero cards, brighter engine names.

Usage: python scripts/landing_shadcn_style.py <bolt_root>
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


# Wider chat box (breadth, not height).
edit("app/styles/variables.scss", "  --chat-max-width: 33rem;", "  --chat-max-width: 52rem;")

# Shadcn-style card: centred content, bright engine label, clear hierarchy.
edit(
    "app/components/chat/BaseChat.tsx",
    """                  <div
                        key={c.name}
                        className="rounded-2xl border border-bolt-elements-borderColor bg-gradient-to-b from-bolt-elements-background-depth-2 to-bolt-elements-background-depth-1 p-7 shadow-sm"
                      >
                        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-bolt-elements-textTertiary">{c.name}</p>
                        <h3 className="mt-2 text-2xl font-bold text-bolt-elements-textPrimary">{c.title}</h3>
                        <p className="mt-4 text-4xl font-extrabold text-white">{c.stat}</p>
                        <p className="text-sm text-bolt-elements-textTertiary">{c.statLabel}</p>
                        <p className="mt-5 text-base leading-relaxed text-bolt-elements-textSecondary">{c.body}</p>
                      </div>""".replace("                  <div\n", "                      <div\n", 1),
    """                      <div
                        key={c.name}
                        className="group flex flex-col items-center rounded-xl border border-bolt-elements-borderColor bg-bolt-elements-background-depth-2 p-8 text-center transition-colors hover:border-[#4d8fe0]"
                      >
                        <span className="inline-flex items-center rounded-full border border-[#4d8fe0]/40 bg-[#4d8fe0]/10 px-3 py-1 text-xs font-semibold text-[#4d8fe0]">
                          {c.name}
                        </span>
                        <h3 className="mt-4 text-xl font-semibold text-bolt-elements-textPrimary">{c.title}</h3>
                        <p className="mt-6 text-4xl font-bold tracking-tight text-bolt-elements-textPrimary">{c.stat}</p>
                        <p className="mt-1 text-sm text-bolt-elements-textSecondary">{c.statLabel}</p>
                        <p className="mt-5 text-sm leading-relaxed text-bolt-elements-textSecondary">{c.body}</p>
                      </div>""",
)

edit(
    "app/components/chat/BaseChat.tsx",
    'className="grid gap-5 md:grid-cols-3 text-left w-full max-w-5xl mx-auto mt-10 px-4"',
    'className="grid gap-5 md:grid-cols-3 text-center w-full max-w-5xl mx-auto mt-10 px-4"',
)
