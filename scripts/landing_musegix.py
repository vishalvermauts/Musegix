"""Musegix landing page: three feature cards, no starter template pills, no stack icons.

Usage: python scripts/landing_musegix.py <bolt_root>
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
edit(base, "import StarterTemplates from './StarterTemplates';\n", "")
edit(base, "import { ExamplePrompts } from '~/components/chat/ExamplePrompts';\n", "")

edit(
    base,
    """                <h1 className="text-3xl lg:text-6xl font-bold text-bolt-elements-textPrimary mb-4 animate-fade-in">
                  Where ideas begin
                </h1>
                <p className="text-md lg:text-xl mb-8 text-bolt-elements-textSecondary animate-fade-in animation-delay-200">
                  Bring ideas to life in seconds or get help on existing projects.
                </p>
""",
    """                <h1 className="text-3xl lg:text-6xl font-bold text-bolt-elements-textPrimary mb-4 animate-fade-in">
                  Musegix
                </h1>
                <p className="text-md lg:text-xl mb-8 text-bolt-elements-textSecondary animate-fade-in animation-delay-200">
                  Build with Meta's models, faster and with less context sent on every step.
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
)

edit(
    base,
    """                {!chatStarted &&
                  ExamplePrompts((event, messageInput) => {
                    if (isStreaming) {
                      handleStop?.();
                      return;
                    }

                    handleSendMessage?.(event, messageInput);
                  })}
                {!chatStarted && <StarterTemplates />}
""",
    "",
)

edit(
    "app/components/chat/ChatBox.tsx",
    "placeholder={props.chatMode === 'build' ? 'How can Bolt help you today?' : 'What would you like to discuss?'}",
    "placeholder={props.chatMode === 'build' ? 'How can Musegix help you today?' : 'What would you like to discuss?'}",
)
