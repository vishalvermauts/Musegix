"""Landing: no scrollbar, one-line headline moved up, 'Auto' label for musecontext-auto.

Usage: python landing_layout.py <bolt_root>
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


BASE = "app/components/chat/BaseChat.tsx"
MS = "app/components/chat/ModelSelector.tsx"

# Headline: one line, moved up.
edit(BASE, 'id="intro" className="mt-[16vh] max-w-2xl mx-auto text-center px-4 lg:px-0"',
     'id="intro" className="mt-[7vh] max-w-3xl mx-auto text-center px-4 lg:px-0"')
edit(BASE, 'className="text-3xl lg:text-5xl font-bold text-bolt-elements-textPrimary mb-3 animate-fade-in"',
     'className="text-3xl lg:text-4xl font-bold whitespace-nowrap text-bolt-elements-textPrimary mb-3 animate-fade-in"')

# Tighter spacing so the page fits without a scrollbar.
edit(BASE, 'className="w-full max-w-5xl mx-auto mt-10 px-4"', 'className="w-full max-w-5xl mx-auto mt-6 px-4"')
edit(BASE, 'className="group flex flex-col items-center rounded-xl border border-bolt-elements-borderColor bg-bolt-elements-background-depth-2 p-8 transition-colors hover:border-[#4d8fe0]"',
     'className="group flex flex-col items-center rounded-xl border border-bolt-elements-borderColor bg-bolt-elements-background-depth-2 p-5 transition-colors hover:border-[#4d8fe0]"')
edit(BASE, '<p className="mt-6 text-4xl font-bold tracking-tight text-bolt-elements-textPrimary">{c.stat}</p>',
     '<p className="mt-4 text-3xl font-bold tracking-tight text-bolt-elements-textPrimary">{c.stat}</p>')
edit(BASE, '<p className="mt-5 text-sm leading-relaxed text-bolt-elements-textSecondary">{c.body}</p>',
     '<p className="mt-3 text-sm leading-relaxed text-bolt-elements-textSecondary">{c.body}</p>')
edit(BASE, 'className="mt-6 rounded-xl border border-bolt-elements-borderColor p-5 text-center"',
     'className="mt-4 rounded-xl border border-bolt-elements-borderColor p-4 text-center"')

# Model label: musecontext-auto shows as 'Auto'.
edit(MS, "<div className=\"truncate\">{modelList.find((m) => m.name === model)?.label || 'Select model'}</div>",
     "<div className=\"truncate\">{model === 'musecontext-auto' ? 'Auto' : modelList.find((m) => m.name === model)?.label || 'Select model'}</div>")
print("done")
