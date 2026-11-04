"""PolyFabric on unnamed-file edits: BM25 target selection + build-artifact stripping."""
from gateway.engines.polyfabric_pruner import PolyFabricPruner, bm25_rank_files, is_build_artifact


def block(path, body):
    return f'<boltAction type="file" filePath="{path}">\n{body}\n</boltAction>'


APP = "export default function App() {\n  return <h1 className='board-title'>Kanban Board</h1>;\n}\n" + "// filler\n" * 40
CSS = ".board-title {\n  color: #fff;\n  font-size: 2rem;\n}\n" + ".x { margin: 0; }\n" * 60
UTIL = "export function formatDate(d) {\n  return d.toISOString();\n}\n" + "// util filler line\n" * 60
BUNDLE = "var a=1;" * 2000  # minified single line

CTX = "<boltArtifact id='p' title='Project'>" + "".join([
    block("/home/project/src/App.jsx", APP),
    block("/home/project/src/index.css", CSS),
    block("/home/project/src/utils/date.js", UTIL),
    block("/home/project/dist/assets/index-abc.js", BUNDLE),
]) + "</boltArtifact>"


def test_build_artifacts_detected():
    assert is_build_artifact("/home/project/dist/assets/index-abc.js", "x")
    assert is_build_artifact("package-lock.json", "{}")
    assert is_build_artifact("src/vendor.js", "a" * 2500)
    assert not is_build_artifact("/home/project/src/App.jsx", APP)


def test_bm25_picks_relevant_files_for_unnamed_edit():
    files = {"src/App.jsx": APP, "src/index.css": CSS, "src/utils/date.js": UTIL}
    top = bm25_rank_files("Change the board title color to orange", files)
    assert "src/utils/date.js" not in top
    assert set(top) <= {"src/App.jsx", "src/index.css"} and top


def test_unnamed_edit_prunes_background_and_drops_bundle():
    res = PolyFabricPruner().prune_context(context_text=CTX, user_prompt="Change the board title color to orange")
    assert "/home/project/src/utils/date.js" in res.pruned_files
    assert "/home/project/dist/assets/index-abc.js" in res.pruned_files
    assert "var a=1;var a=1;" not in res.pruned_text
    # target bodies untouched (Target File Invariant)
    for kept in res.preserved_files:
        assert kept.endswith(("App.jsx", "index.css"))
    assert res.reduction_pct > 50
    assert res.pruned_text.count("<boltAction") == 4  # tags preserved


def test_no_query_terms_keeps_sources_but_still_drops_bundle():
    res = PolyFabricPruner().prune_context(context_text=CTX, user_prompt="do it")
    assert "/home/project/src/utils/date.js" in res.preserved_files
    assert "/home/project/dist/assets/index-abc.js" in res.pruned_files
