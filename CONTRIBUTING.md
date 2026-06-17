# Contributing

SpatialScope Agent is maintained as a reproducible analysis product. Changes
should keep the core workflow runnable, inspectable, and scientifically cautious.

## Local Checks

Before pushing:

```bash
scripts/check_project.sh
git status -sb
```

The check script runs unit tests and a CLI smoke demo. It should pass before
opening a pull request or preparing a presentation build.

## Development Flow

Small fixes can land directly on `main` during active solo development. Larger
changes should use a branch:

```bash
git checkout -b feature/<topic>
```

Preferred commit prefixes:

- `feat:` visible feature or product improvement
- `fix:` bug fix
- `docs:` documentation, GitHub Pages, or project materials
- `test:` tests and fixtures
- `chore:` repository maintenance

## Scientific Guardrails

- Do not send raw expression matrices or raw coordinate matrices to an LLM.
- Prefer deterministic tool outputs over generated claims.
- Mark optional or fragile analyses as optional.
- Report warnings and limitations in user-facing outputs.
- Treat cluster labels as candidate annotations unless independently validated.

## UI Guardrails

- Keep the first screen an actual workspace, not a marketing landing page.
- Keep technical English where it is the natural term: `AnnData`, `QC`, `UMAP`,
  `Leiden`, `LangGraph`, `trace`, `report`.
- Avoid hiding errors behind polished visuals.
- Preserve downloadability for reports, metadata, parameters, figures, and trace.

## Pull Request Checklist

- [ ] Unit tests pass.
- [ ] CLI smoke demo passes.
- [ ] New tool behavior has a contract or schema validation where appropriate.
- [ ] Warnings/errors are visible in UI or report.
- [ ] README or docs are updated for user-facing changes.
