"""Apply rubric v1 to the bolt-style label set.

Rubric v1 (from the user):
- TRIVIAL: small, clearly scoped change to existing code (colours, fonts, spacing, text).
- MODERATE: bounded feature or page, a few files, no new backend, security design or architecture.
- HARD: security-sensitive behaviour, new systems, migrations, distributed coordination, or
  substantial architectural reasoning. These override file count.
- Judge the requested work, not keywords.

Outputs:
- data/labels/bolt_style/reviewed.jsonl     (label_source = reviewed_rubric_v1_assistant)
- data/labels/bolt_style/needs_context.jsonl (review_status = needs_context, kept, not trained on)
- data/labels/bolt_style/review_changes.md   (every changed label with its reason)
"""
import collections
import json
import os

RUBRIC = "v1"
SRC = "data/labels/bolt_style/labels.jsonl"
OUT = "data/labels/bolt_style"

# Changed labels: prompt -> (new_label, reason). Everything else keeps the draft label after review.
CHANGES = {
    "Add a simple authentication guard that redirects logged-out users to login.":
        ("hard", "Security-sensitive behaviour (access control on routes). Rubric: security overrides size."),
    "Create a login page with email and password fields and a remember-me checkbox.":
        ("moderate", "Kept MODERATE: UI form only, no real authentication backend in scope. Note: security-adjacent."),
}

# Ambiguous: preserved in needs_context.jsonl with an explanation.
NEEDS_CONTEXT = {
    "Add multi-step form autosave with merge conflicts and draft recovery after a crash.":
        "Depends on storage (local vs server) and how many users edit one draft. Local-only autosave is MODERATE; server sync with merge is HARD.",
    "Add accessibility compliance with keyboard navigation, screen reader support and an automated audit.":
        "Scope is unclear: a few components (MODERATE) or whole-app audit tooling (HARD).",
    "Add internationalisation with plural rules, right-to-left layout and lazy-loaded locales.":
        "Depends on how many screens and whether locales come from a service. Could be MODERATE for one language, HARD for full i18n.",
}

# Family groups used for splitting. Order matters: the first matching keyword wins.
FAMILY_RULES = [
    ("auth-security", ["auth", "login", "jwt", "oauth", "two-factor", "encrypt", "signing", "permission", "role", "access", "guard", "password", "audit trail", "tamper"]),
    ("billing-commerce", ["billing", "stripe", "payment", "invoice", "currency", "checkout", "marketplace", "pricing", "reconciliation", "auction", "booking", "fraud"]),
    ("realtime-sync", ["real-time", "websocket", "collaborat", "live", "sync", "offline", "server-sent", "whiteboard", "optimistic", "crdt", "conflict"]),
    ("data-platform", ["postgres", "database", "migrat", "import", "export", "warehouse", "retention", "cache", "caching", "redis", "index", "search", "vector", "telemetry", "recommendation", "reporting", "event-sourced"]),
    ("services-infra", ["kubernetes", "ci/cd", "deploy", "observability", "failover", "service", "gateway", "grpc", "graphql", "api", "plugin", "workflow", "queue", "job", "scheduling", "mobile", "multi-tenant", "tenant", "rate limiting", "email", "notification", "undo", "code-generation", "feature flag", "pipeline"]),
    ("product-ui", ["dark", "form", "table", "page", "modal", "navbar", "footer", "chart", "toast", "gallery", "card", "tab", "tooltip", "upload", "calendar", "stepper", "wizard", "quiz", "rating", "banner", "feedback", "search bar", "leaderboard", "todo", "notes", "kanban", "counter", "faq", "timer", "breadcrumb", "pagination", "sorting", "filter", "drag", "accordion", "language", "share", "countdown", "empty state", "loading", "progress", "confirm", "print", "lightbox", "onboarding", "profile", "settings", "keyboard", "dropdown", "recipe", "booking", "expense", "scroll", "feed"]),
]


def family_of(prompt):
    low = prompt.lower()
    for name, words in FAMILY_RULES:
        if any(w in low for w in words):
            return name
    return "other"


# Trivial examples: small changes to existing code. Each is self-contained (router sees only this text).
TRIVIAL = [
    "Change the primary button colour from blue to green.",
    "Change the page title font to Inter and make it bold.",
    "Increase the spacing between the cards on the dashboard to 24px.",
    "Change the footer text to say 'Copyright 2026 Acme Inc.'",
    "Make the sidebar background darker grey.",
    "Change the heading 'Welcome back' to 'Good to see you'.",
    "Make the logo 20% smaller in the header.",
    "Change the error message colour to red on the login form.",
    "Change the card border radius to 12px.",
    "Change the body font size to 16px.",
    "Fix the typo 'Recieve' to 'Receive' on the orders page.",
    "Change the button label Submit to Save changes.",
    "Make the navbar text white instead of black.",
    "Change the background of the pricing section to light blue.",
    "Center the page heading.",
    "Make the table row hover colour light grey.",
    "Change the link colour in the footer to orange.",
    "Add a 1px grey divider under the header.",
    "Change the placeholder text in the search box to 'Search customers'.",
    "Change the Done column header colour to purple.",
    "Make the tab labels uppercase.",
    "Change the success toast text to 'Saved'.",
    "Make the weather icon larger on the card.",
    "Change the app name in the header to MetaDesk.",
    "Set the page background to a light beige.",
    "Make the main heading bold and 32px.",
    "Change the title of the Settings page to 'Preferences'.",
    "Reduce the padding inside the stat cards to 12px.",
    "Change the active menu item background to light purple.",
    "Make the copyright text smaller and grey.",
    "Change the label 'Remember me' to 'Keep me signed in'.",
    "Change the badge colour for the 'Paid' status to green.",
    "Change the chart line colour to teal.",
    "Round the corners of the avatar images.",
    "Change the sign up button text to 'Create account'.",
    "Make the price text in the plan card bigger.",
    "Change the empty state text to 'No results yet'.",
    "Change the default theme colour to dark blue.",
    "Make the icons in the sidebar slightly bigger.",
    "Change the table header text to dark grey.",
    "Swap the position of the search box and the filter button.",
    "Change the notification badge colour to red.",
    "Make the input borders thicker on focus.",
    "Change the hover colour of the Add button to darker blue.",
    "Change the description text under the title to italic.",
    "Shorten the tagline on the home page to 'Work smarter'.",
    "Change the line height of the paragraph text to 1.6.",
    "Change the icon of the Team menu item to a people icon.",
    "Make the text on the hero section white.",
    "Change the date format on the invoices page to DD/MM/YYYY.",
    "Change the currency symbol on the billing page to pounds.",
    "Make the cancel button grey instead of red.",
]

# Realistic follow-ups. Written so the router can classify them without extra context.
FOLLOWUPS = [
    ("trivial", "On the Billing page, make the plan card borders purple too."),
    ("trivial", "Apply the same green colour to the Customers page save button as well."),
    ("trivial", "Change the Tickets page title to Support, the same as the sidebar item."),
    ("trivial", "Make the same card shadow we used on the Dashboard appear on the Team page cards."),
    ("moderate", "Add the same search bar to the Tickets page, filtering tickets by subject."),
    ("moderate", "Add a sort dropdown to the Customers table with name, plan and joined date."),
    ("moderate", "Add a delete button to each row of the Team table that asks for confirmation first."),
    ("hard", "Make the Customers table load from the API with server-side paging and filters."),
]


def main():
    rows = [json.loads(l) for l in open(SRC, encoding="utf-8")]
    reviewed, needs, changes = [], [], []
    for r in rows:
        p = r["prompt"]
        fam = family_of(p)
        if p in NEEDS_CONTEXT:
            needs.append({"prompt": p, "draft_label": r["label"], "review_status": "needs_context",
                          "explanation": NEEDS_CONTEXT[p], "family": fam, "rubric": RUBRIC})
            continue
        label, reason = r["label"], None
        if p in CHANGES:
            new, reason = CHANGES[p]
            if new != label:
                changes.append((p, label, new, reason))
            label = new
        reviewed.append({"prompt": p, "label": label, "label_source": "reviewed_rubric_v1_assistant",
                         "family": fam, "rubric": RUBRIC, "change_reason": reason})
    for p in TRIVIAL:
        reviewed.append({"prompt": p, "label": "trivial", "label_source": "reviewed_rubric_v1_assistant",
                         "family": "ui-style", "rubric": RUBRIC, "change_reason": None})
    for label, p in FOLLOWUPS:
        reviewed.append({"prompt": p, "label": label, "label_source": "reviewed_rubric_v1_assistant",
                         "family": "ui-style" if label == "trivial" else family_of(p), "rubric": RUBRIC, "change_reason": "realistic follow-up, self-contained"})

    os.makedirs(OUT, exist_ok=True)
    with open(f"{OUT}/reviewed.jsonl", "w", encoding="utf-8") as fh:
        for r in reviewed:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(f"{OUT}/needs_context.jsonl", "w", encoding="utf-8") as fh:
        for r in needs:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(f"{OUT}/review_changes.md", "w", encoding="utf-8") as fh:
        fh.write(f"# Label review, rubric {RUBRIC}\n\n")
        fh.write("Labels were applied by the assistant against the rubric; a human spot-check is still needed.\n\n")
        fh.write("## Changed labels\n\n")
        for p, old, new, reason in changes:
            fh.write(f"- `{old}` -> `{new}`: {p}  \n  Reason: {reason}\n")
        fh.write("\n## Moved to needs_context\n\n")
        for r in needs:
            fh.write(f"- {r['prompt']}  \n  Reason: {r['explanation']}\n")

    print("reviewed:", len(reviewed), collections.Counter(r["label"] for r in reviewed))
    print("needs_context:", len(needs))
    print("changed:", len(changes))
    print("families:", collections.Counter(r["family"] for r in reviewed))


if __name__ == "__main__":
    main()
