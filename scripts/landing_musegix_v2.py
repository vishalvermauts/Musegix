"""Musegix landing v2: engine-named feature cards, measured stats line, taller chat box.

Usage: python scripts/landing_musegix_v2.py <bolt_root>
"""
import pathlib
import sys

root = pathlib.Path(sys.argv[1])


def edit(rel, old, new):
    p = root / rel
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (rel, s.count(old), old[:70])
    p.write_text(s.replace(old, new), encoding="utf-8")
    print("edited", rel)


base = "app/components/chat/BaseChat.tsx"
card = "rounded-xl border border-bolt-elements-borderColor bg-bolt-elements-background-depth-2 p-5"

edit(base, "const TEXTAREA_MIN_HEIGHT = 76;", "const TEXTAREA_MIN_HEIGHT = 120;")

edit(
    base,
    """                  Build with Meta's models, faster and with less context sent on every step.
                </p>
                <div className="grid gap-4 sm:grid-cols-3 text-left mt-6">
                  <div className="rounded-xl border border-bolt-elements-borderColor bg-bolt-elements-background-depth-2 p-5">
                    <h3 className="font-semibold text-bolt-elements-textPrimary mb-2">Smart routing</h3>
                    <p className="text-sm text-bolt-elements-textSecondary">
                      Each prompt is classified in milliseconds. Simple edits go to a cheaper model; harder work goes to a stronger one.
                    </p>
                  </div>
                  <div className="rounded-xl border border-bolt-elements-borderColor bg-bolt-elements-background-depth-2 p-5">
                    <h3 className="font-semibold text-bolt-elements-textPrimary mb-2">Context trimming</h3>
                    <p className="text-sm text-bolt-elements-textSecondary">
                      Old tool output and unrelated files are trimmed before each request, so fewer tokens are sent on every step.
                    </p>
                  </div>
                  <div className="rounded-xl border border-bolt-elements-borderColor bg-bolt-elements-background-depth-2 p-5">
                    <h3 className="font-semibold text-bolt-elements-textPrimary mb-2">Impact checks</h3>
                    <p className="text-sm text-bolt-elements-textSecondary">
                      When an exported function or component changes, Musegix lists the other files that still use it.
                    </p>
                  </div>
                </div>
""",
    f"""                  Build with Meta's models, faster and with less context sent on every step.
                </p>
                <div className="grid gap-4 sm:grid-cols-3 text-left mt-6">
                  <div className="{card}">
                    <p className="text-xs font-mono uppercase tracking-wider text-bolt-elements-textTertiary mb-1">Ysolveth</p>
                    <h3 className="font-semibold text-bolt-elements-textPrimary mb-2">Smart routing</h3>
                    <p className="text-sm text-bolt-elements-textSecondary">
                      Classifies every prompt in about 5 ms on CPU. Simple edits go to a cheaper model; harder work goes to a stronger one.
                    </p>
                  </div>
                  <div className="{card}">
                    <p className="text-xs font-mono uppercase tracking-wider text-bolt-elements-textTertiary mb-1">PolyFabric</p>
                    <h3 className="font-semibold text-bolt-elements-textPrimary mb-2">Context trimming</h3>
                    <p className="text-sm text-bolt-elements-textSecondary">
                      Cuts old tool output by about 95% and sends only the files a request needs.
                    </p>
                  </div>
                  <div className="{card}">
                    <p className="text-xs font-mono uppercase tracking-wider text-bolt-elements-textTertiary mb-1">Veylqora</p>
                    <h3 className="font-semibold text-bolt-elements-textPrimary mb-2">Impact checks</h3>
                    <p className="text-sm text-bolt-elements-textSecondary">
                      Tracks every function and component. When an export changes, it lists the files that still use it.
                    </p>
                  </div>
                </div>
                <p className="mt-5 text-xs font-mono tracking-wide text-bolt-elements-textTertiary">
                  three engines · one gateway · Meta models in the browser IDE
                </p>
""",
)
