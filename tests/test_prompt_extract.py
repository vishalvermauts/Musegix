from gateway.prompt_extract import clean_user_prompt, latest_user_prompt

WRAPPED = "[Model: musecontext-auto]\n\n[Provider: OpenAILike]\n\nChange the title color to orange."


def test_strips_bolt_model_and_provider_header():
    assert clean_user_prompt(WRAPPED) == "Change the title color to orange."


def test_plain_prompt_unchanged():
    assert clean_user_prompt("Fix the typo") == "Fix the typo"


def test_prefers_typed_message_over_synthetic_user_message():
    msgs = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": WRAPPED},
        {"role": "user", "content": "Bolt is initializing your project with the required files."},
    ]
    assert latest_user_prompt(msgs) == "Change the title color to orange."


def test_list_content_parts():
    msgs = [{"role": "user", "content": [{"type": "text", "text": WRAPPED}, {"type": "image", "image": "x"}]}]
    assert latest_user_prompt(msgs) == "Change the title color to orange."


def test_fallback_without_header():
    assert latest_user_prompt([{"role": "user", "content": "Add an About page"}]) == "Add an About page"


def test_bolt_updated_files_snapshot_is_not_the_prompt():
    from gateway.prompt_extract import latest_user_prompt
    msgs = [
        {"role": "user", "content": "[Model: m]\n\n[Provider: p]\n\nRename the app to MetaDesk."},
        {"role": "user", "content": "[Model: m]\n\n[Provider: p]\n\n\n<boltArtifact id=\"1\" title=\"User Updated Files\">\n<boltAction type=\"file\" filePath=\"a.tsx\">x</boltAction></boltArtifact>"},
    ]
    assert latest_user_prompt(msgs) == "Rename the app to MetaDesk."


def test_typed_request_after_artifact_snapshot_is_extracted():
    from gateway.prompt_extract import latest_user_prompt
    msgs = [{"role": "user", "content": "[Model: m]\n\n[Provider: p]\n\n\n<boltArtifact id=\"1\"><boltAction type=\"file\" filePath=\"a.tsx\">const x = 1;</boltAction></boltArtifact>\n  Rename the app to MetaDesk."}]
    assert latest_user_prompt(msgs) == "Rename the app to MetaDesk."
