import os, tempfile
from gateway.engines.veylqora_guard import VeylqoraGuard


def _g():
    return VeylqoraGuard(os.path.join(tempfile.mkdtemp(), "v.db"))


APP = "export default function App() {\n  return <h1>Hi</h1>;\n}\n"


def test_no_change_between_turns_is_active():
    g = _g()
    g.inspect_turn("s", {"src/App.jsx": APP})
    assert g.inspect_turn("s", {"src/App.jsx": APP}).stale_count == 0


def test_edited_symbol_is_flagged_and_unedited_is_not():
    g = _g()
    other = "export function util() { return 1; }\n"
    g.inspect_turn("s", {"src/App.jsx": APP, "src/u.js": other})
    r = g.inspect_turn("s", {"src/App.jsx": APP.replace("Hi", "Yo"), "src/u.js": other})
    assert r.status == "SUSPECTED_STALE"
    assert {m.file_path for m in r.mutated_symbols} == {"src/App.jsx"}


def test_sessions_are_isolated():
    g = _g()
    g.inspect_turn("a", {"f.js": "var a=1;"})
    assert g.inspect_turn("b", {"f.js": "var a=2;"}).stale_count == 0
