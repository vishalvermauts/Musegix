"""Musegix landing per the approved copy spec. Usage: python landing_spec.py <bolt_root>"""
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
BASE = "app/components/chat/BaseChat.tsx"
CHAT = "app/components/chat/ChatBox.tsx"
SEND = "app/components/chat/SendButton.client.tsx"


def rw(rel):
    return root / rel


def edit(rel, old, new, count=1):
    p = rw(rel)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == count, (rel, s.count(old), old[:70])
    p.write_text(s.replace(old, new), encoding="utf-8")
    print("edited", rel)


# 1. Hero headline and paragraph.
s = rw(BASE).read_text(encoding="utf-8")
start = s.index('                <h1 className="text-3xl lg:text-6xl')
end = s.index('                </p>\n', start) + len('                </p>\n')
HERO = (
    '                <h1 className="text-3xl lg:text-5xl font-bold text-bolt-elements-textPrimary mb-3 animate-fade-in">\n'
    '                  Build your idea. Refine every detail.\n'
    '                </h1>\n'
    '                <p className="text-md lg:text-lg mb-6 text-bolt-elements-textSecondary animate-fade-in animation-delay-200 max-w-2xl mx-auto">\n'
    '                  Create apps with Meta AI. From your first build to your next edit, Musegix automatically selects a model suited to the task.\n'
    '                </p>\n'
)
s = s[:start] + HERO + s[end:]
rw(BASE).write_text(s, encoding="utf-8")
print("edited", BASE, "(hero)")

# 2. Compact feature cards and the benchmark section.
s = rw(BASE).read_text(encoding="utf-8")
cstart = s.index('                {!chatStarted && (\n                  <div className="grid gap-5 md:grid-cols-3')
cend = s.index("                )}\n", cstart) + len("                )}\n")
CARDS = (
    '                {!chatStarted && (\n'
    '                  <div className="w-full max-w-4xl mx-auto mt-6 px-4">\n'
    '                    <div className="grid gap-3 md:grid-cols-3 text-left">\n'
    '                      {[\n'
    "                        { name: 'Ysolveth', title: 'Smart routing. Every turn.',\n"
    "                          body: 'A trained local model assesses each request, routing simple edits to fast models and complex work to stronger reasoning.' },\n"
    "                        { name: 'PolyFabric', title: 'Focused context. Less waste.',\n"
    "                          body: 'Keeps relevant project context in focus and trims older file reads and command logs before they reach the model.' },\n"
    "                        { name: 'Veylqora', title: 'See what your changes affect.',\n"
    "                          body: 'Tracks code fingerprints and highlights dependent files that may need attention when symbols change.' },\n"
    '                      ].map((c) => (\n'
    '                        <div key={c.name} className="rounded-xl border border-bolt-elements-borderColor bg-bolt-elements-background-depth-2 p-4">\n'
    '                          <span className="inline-flex rounded-full border border-bolt-elements-borderColor px-2 py-0.5 text-[11px] font-medium text-bolt-elements-textSecondary">\n'
    '                            {c.name}\n'
    '                          </span>\n'
    '                          <h3 className="mt-2 text-sm font-semibold text-bolt-elements-textPrimary">{c.title}</h3>\n'
    '                          <p className="mt-1 text-xs leading-relaxed text-bolt-elements-textSecondary">{c.body}</p>\n'
    '                        </div>\n'
    '                      ))}\n'
    '                    </div>\n'
    '                    <div className="mt-6 text-left rounded-xl border border-bolt-elements-borderColor p-4">\n'
    '                      <p className="text-xs font-semibold uppercase tracking-wider text-bolt-elements-textTertiary">Benchmark results</p>\n'
    '                      <ul className="mt-2 space-y-1 text-xs text-bolt-elements-textSecondary">\n'
    '                        <li>≈2–6 ms: Ysolveth routing time on CPU, warm calls (evidence: benchmarks/benchmark_results.json)</li>\n'
    '                        <li>≈95% less old tool output sent, across our test runs. Not a total token saving.</li>\n'
    '                        <li>100% of mutated background symbols flagged, in our test set. Not a general guarantee.</li>\n'
    '                      </ul>\n'
    '                    </div>\n'
    '                  </div>\n'
    '                )}\n'
)
s = s[:cstart] + CARDS + s[cend:]
rw(BASE).write_text(s, encoding="utf-8")
print("edited", BASE, "(cards and benchmark)")

# 3. Clickable suggestions below the composer.
s = rw(BASE).read_text(encoding="utf-8")
anchor = '              <div className="flex flex-col gap-5">\n'
assert s.count(anchor) == 1, s.count(anchor)
SUGG = (
    anchor
    + '                {!chatStarted && (\n'
    + '                  <div className="flex flex-wrap justify-center gap-2">\n'
    + "                    {['Business dashboard', 'Booking app', 'Portfolio website', 'Online store'].map((label) => (\n"
    + '                      <button\n'
    + '                        key={label}\n'
    + '                        onClick={(event) => handleSendMessage?.(event, `Build a ${label.toLowerCase()}.`)}\n'
    + '                        className="rounded-full border border-bolt-elements-borderColor px-3 py-1 text-xs text-bolt-elements-textSecondary hover:text-bolt-elements-textPrimary transition-colors"\n'
    + '                      >\n'
    + '                        {label}\n'
    + '                      </button>\n'
    + '                    ))}\n'
    + '                  </div>\n'
    + '                )}\n'
)
s = s.replace(anchor, SUGG, 1)
rw(BASE).write_text(s, encoding="utf-8")
print("edited", BASE, "(suggestions)")

# 4. Composer: placeholder, Build app / Send button.
edit(CHAT,
     "placeholder={props.chatMode === 'build' ? 'How can Musegix help you today?' : 'What would you like to discuss?'}",
     "placeholder={props.chatMode === 'build' ? 'Describe what you want to build or change…' : 'What would you like to discuss?'}")
edit(CHAT,
     "            <SendButton\n              show={props.input.length > 0 || props.isStreaming || props.uploadedFiles.length > 0}\n              isStreaming={props.isStreaming}",
     "            <SendButton\n              show={!props.chatStarted || props.input.length > 0 || props.isStreaming || props.uploadedFiles.length > 0}\n              label={props.chatStarted ? 'Send →' : 'Build app →'}\n              isStreaming={props.isStreaming}")
edit(SEND, "interface SendButtonProps {\n", "interface SendButtonProps {\n  label?: string;\n")
edit(SEND,
     "export const SendButton = ({ show, isStreaming, disabled, onClick }: SendButtonProps) => {",
     "export const SendButton = ({ show, label = 'Send →', isStreaming, disabled, onClick }: SendButtonProps) => {")
edit(SEND,
     'className="absolute flex justify-center items-center top-[18px] right-[22px] p-1 bg-accent-500 hover:brightness-94 color-white rounded-md w-[34px] h-[34px] transition-theme disabled:opacity-50 disabled:cursor-not-allowed"',
     'className="absolute flex justify-center items-center bottom-[14px] right-[14px] gap-2 px-4 h-[38px] bg-accent-500 hover:brightness-110 text-white text-sm font-semibold rounded-lg shadow-md transition-theme disabled:opacity-50 disabled:cursor-not-allowed"')
edit(SEND,
     '          <div className="text-lg">\n            {!isStreaming ? <div className="i-ph:arrow-right"></div> : <div className="i-ph:stop-circle-bold"></div>}\n          </div>',
     '          {isStreaming ? <div className="i-ph:stop-circle-bold text-lg"></div> : <span>{label}</span>}')

# 5. Import actions as secondary wording.
edit("app/components/chat/ImportFolderButton.tsx", 'title="Import Folder"', 'title="Open folder"')
edit("app/components/chat/ImportFolderButton.tsx", "'Import Folder'}", "'Open folder'}")
edit("app/components/chat/ImportZipButton.tsx", 'title="Import ZIP"', 'title="Upload ZIP"')
edit("app/components/chat/ImportZipButton.tsx", "'Import ZIP'}", "'Upload ZIP'}")
edit("app/components/chat/GitCloneButton.tsx", 'title="Clone a repo"', 'title="Clone repository"')
edit("app/components/chat/GitCloneButton.tsx", "        Clone a repo\n", "        Clone repository\n")

# 6. Permissions label and provider display name.
edit("app/components/chat/ToolAccessMenu.tsx", "label: 'Full Access'", "label: 'Permissions: Full access'")
edit("app/components/chat/ModelSelector.tsx",
     "const displayProviderName = (name?: string) => (name === 'OpenAILike' ? 'Meta Model' : name);",
     "const displayProviderName = (name?: string) => (name === 'OpenAILike' ? 'Meta AI' : name);")
print("done")
