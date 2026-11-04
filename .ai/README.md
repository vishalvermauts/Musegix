# AI Project Memory System

This folder contains persistent AI memory for this workspace.

## Startup Workflow
Every session, the AI assistant reads the files in the root of this directory in order:
1. `README.md`
2. `CONSTRAINTS.md`
3. `manifest.json`
4. `session.md`
5. `summary.md`

Only read documentation files inside `docs/` if the active task specifically requires them. Do not read them automatically.
