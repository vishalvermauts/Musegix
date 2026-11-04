from gateway.streaming import is_auxiliary_request

MAIN_SYSTEM = "You are Bolt, an expert AI assistant.\n" + ("rules\n" * 300) + "CHAT SUMMARY:\n---\n# Project Overview"
SUMMARY_SYSTEM = ("You are a software engineer. You are working on a project. you need to summarize the work "
                  "till now and provide a summary of the chat till now.")


def test_main_agent_step_with_chat_summary_section_is_not_auxiliary():
    body = {"tools": [{"type": "function", "function": {"name": "project_read_file"}}],
            "messages": [{"role": "system", "content": MAIN_SYSTEM}, {"role": "user", "content": "Make it green"}]}
    assert is_auxiliary_request(body) is False


def test_main_prompt_without_tools_deep_summary_section_is_not_auxiliary():
    body = {"messages": [{"role": "system", "content": MAIN_SYSTEM}, {"role": "user", "content": "Make it green"}]}
    assert is_auxiliary_request(body) is False


def test_bolt_summary_call_is_auxiliary():
    body = {"messages": [{"role": "system", "content": SUMMARY_SYSTEM}, {"role": "user", "content": "chat..."}]}
    assert is_auxiliary_request(body) is True
