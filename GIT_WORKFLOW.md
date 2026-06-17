# Git Workflow

This repository uses GitHub as the source of truth for code, project documentation,
and the public static project site.

## Branches

- `main`: stable branch. It should remain runnable, tested, and presentation-ready.
- `feature/<topic>`: optional development branch for larger changes.
- `docs/<topic>`: optional documentation or GitHub Pages updates.

Small, low-risk fixes can be committed directly to `main` while the project is in
active solo development. Larger changes should use a feature branch and a Pull
Request before merging.

## Commit Style

Use short conventional commit prefixes:

- `feat:` new feature or visible product improvement
- `fix:` bug fix
- `docs:` documentation or GitHub Pages content
- `test:` tests or test data changes
- `chore:` dependency, config, or repository maintenance

Examples:

```bash
git commit -m "feat: add spatial atlas project site"
git commit -m "fix: guard missing spatial coordinates"
git commit -m "docs: document GitHub Pages deployment"
```

## Before Pushing

Run:

```bash
scripts/check_project.sh
git status -sb
```

The check script runs unit tests and a CLI smoke demo. It should pass before a
presentation or tagged milestone.

## GitHub Automation

- `.github/workflows/ci.yml` runs tests and the CLI smoke demo.
- `.github/workflows/pages.yml` deploys the static site from `docs/`.

For GitHub Pages, configure the repository once:

1. Open repository Settings.
2. Go to Pages.
3. Set Source to GitHub Actions.
4. Trigger the `GitHub Pages` workflow or push to `main`.

The expected public site URL is:

```text
https://seu-yolo.github.io/spatialscope-agent/
```

## What Not To Commit

Do not commit:

- `.env` or API keys
- full `.h5ad` datasets
- `outputs/runs/`
- temporary upload files
- Python caches and local test artifacts

These are covered by `.gitignore`.
