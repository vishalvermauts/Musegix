"""Does bolt.diy's message wrapper change Ysolveth's routing decision?

Classifies each prompt raw, then wrapped exactly the way bolt.diy sends it
("[Model: ...]\n\n[Provider: ...]\n\n<prompt>"), and reports tier flips.
Run:  python scripts/ysolveth_wrapper_check.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gateway.engines.ysolveth_classifier import YsolvethClassifier  # noqa: E402
from gateway.prompt_extract import clean_user_prompt  # noqa: E402

WRAP = "[Model: musecontext-auto]\n\n[Provider: OpenAILike]\n\n{}"

PROMPTS = [
    "Change the Kanban Board title color to orange.",
    "Fix the typo in the footer text.",
    "Make the submit button bigger.",
    "Rename the 'Done' column to 'Finished'.",
    "Change the logo to a blue circle.",
    "Add a dark mode toggle to the header.",
    "Add form validation to the signup form with error messages.",
    "Create a useLocalStorage hook and persist the board state.",
    "Add a search bar that filters cards by title.",
    "Build a todo app with React.",
    "Create a Kanban board in React with three columns: To Do, In Progress, Done. Let me add cards and move them between columns.",
    "Build a portfolio website with a projects gallery and contact form.",
    "Add user authentication with JWT, protected routes and refresh tokens.",
    "Refactor the app to use a Redux store with slices for boards, cards and users.",
    "Add real-time collaboration over WebSockets so multiple users see card moves live.",
    "Migrate the data layer to a multi-tenant Postgres schema with row-level security.",
    "Integrate Stripe subscriptions with webhook reconciliation and retries.",
    "Split the monolith into three services with a message queue between them.",
    "Center the heading.",
    "Add an About page.",
]


def main() -> None:
    clf = YsolvethClassifier()
    flips = 0
    print(f"{'raw':9} {'wrapped':9} {'cleaned':9}  prompt")
    for p in PROMPTS:
        raw = clf.classify(p)
        wrapped_text = WRAP.format(p)
        wr = clf.classify(wrapped_text)
        cl = clf.classify(clean_user_prompt(wrapped_text))
        flag = " <-- FLIP" if raw["tier"] != wr["tier"] else ""
        flips += bool(flag)
        print(f"{raw['tier']:9} {wr['tier']:9} {cl['tier']:9}  {p[:70]}{flag}")
    print(f"\n{flips}/{len(PROMPTS)} prompts change tier when bolt.diy's wrapper is left in.")


if __name__ == "__main__":
    main()
