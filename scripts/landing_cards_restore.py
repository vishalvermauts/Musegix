"""Restore the centred stat cards and keep the benchmark box below them (per user feedback).

Usage: python landing_cards_restore.py <bolt_root>
"""
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
BASE = root / "app/components/chat/BaseChat.tsx"
s = BASE.read_text(encoding="utf-8")

start_marker = '                {!chatStarted && (\n                  <div className="w-full max-w-4xl mx-auto mt-6 px-4">'
assert s.count(start_marker) == 1, s.count(start_marker)
start = s.index(start_marker)
end = s.index("                )}\n", start) + len("                )}\n")

NEW = '''                {!chatStarted && (
                  <div className="w-full max-w-5xl mx-auto mt-10 px-4">
                    <div className="grid gap-5 md:grid-cols-3 text-center">
                      {[
                        { name: 'Ysolveth', title: 'Smart routing. Every turn.', stat: '≈2–6 ms', statLabel: 'CPU routing time per prompt',
                          body: 'A trained local model assesses each request, routing simple edits to fast models and complex work to stronger reasoning.' },
                        { name: 'PolyFabric', title: 'Focused context. Less waste.', stat: '≈95%', statLabel: 'less old tool output sent',
                          body: 'Keeps relevant project context in focus and trims older file reads and command logs before they reach the model.' },
                        { name: 'Veylqora', title: 'See what your changes affect.', stat: '100%', statLabel: 'mutated symbols flagged in our test set',
                          body: 'Tracks code fingerprints and highlights dependent files that may need attention when symbols change.' },
                      ].map((c) => (
                        <div
                          key={c.name}
                          className="group flex flex-col items-center rounded-xl border border-bolt-elements-borderColor bg-bolt-elements-background-depth-2 p-8 transition-colors hover:border-[#4d8fe0]"
                        >
                          <span className="inline-flex items-center rounded-full border border-[#4d8fe0]/40 bg-[#4d8fe0]/10 px-3 py-1 text-xs font-semibold text-[#4d8fe0]">
                            {c.name}
                          </span>
                          <h3 className="mt-4 text-xl font-semibold text-bolt-elements-textPrimary">{c.title}</h3>
                          <p className="mt-6 text-4xl font-bold tracking-tight text-bolt-elements-textPrimary">{c.stat}</p>
                          <p className="mt-1 text-sm text-bolt-elements-textSecondary">{c.statLabel}</p>
                          <p className="mt-5 text-sm leading-relaxed text-bolt-elements-textSecondary">{c.body}</p>
                        </div>
                      ))}
                    </div>
                    <div className="mt-6 rounded-xl border border-bolt-elements-borderColor p-5 text-center">
                      <p className="text-xs font-semibold uppercase tracking-wider text-bolt-elements-textTertiary">Benchmark results</p>
                      <ul className="mt-3 space-y-1 text-xs text-bolt-elements-textSecondary">
                        <li>Routing: warm CPU calls, measured in benchmarks/benchmark_results.json</li>
                        <li>Old tool output: about 95% less across our test runs. Not a total token saving.</li>
                        <li>Veylqora: 100% of mutated background symbols flagged in our test set. Not a general guarantee.</li>
                      </ul>
                    </div>
                  </div>
                )}
'''

s = s[:start] + NEW + s[end:]
BASE.write_text(s, encoding="utf-8")
print("restored cards in", BASE)
