# SpatialScope v6 Visual Review

## Screenshots reviewed

- `docs/assets/v6-landing-empty-1440.png`
- `docs/assets/v6-landing-empty-1024.png`
- `docs/assets/v6-landing-mobile.png`
- `docs/assets/v6-project-dataset-ready.png`
- `docs/assets/v6-project-plan-ready.png`
- `docs/assets/v6-run-live.png`
- `docs/assets/v6-explore-workspace.png`
- `docs/assets/v6-report-editorial.png`

## Defects found during browser review

1. The first Project screenshots showed the active dataset header clipped under Streamlit's top navigation.
2. The Explore workspace initially exposed Plotly modebars and left the Copilot answer below the first viewport.
3. The Report page originally used interactive dataframes, which introduced low-level table controls in the main editorial surface.
4. Mobile capture needed to prove the real embryo preview remained readable in the narrow layout.

## Fixes made after review

1. Added extra active-header spacing so dataset pages render cleanly below Streamlit navigation.
2. Hid Plotly modebars in the main evidence canvas and moved the latest Copilot answer above the next-question controls.
3. Replaced main Report dataframes with static editorial tables; individual artifact controls stay in Advanced.
4. Regenerated the mobile screenshot at narrow width with enough height to show composer, CTA, and the real spatial preview.

## Browser-visible acceptance notes

- Empty Project has one primary CTA, no QC form, no provider details, and a real embryo preview.
- Demo selection fills the dataset and recommended research question but does not auto-run.
- Dataset-ready Project shows inspected facts, resolved genes, caveat, and a vertical reviewable plan without JSON editing.
- Run shows a live LangGraph event timeline and current-step panel instead of a single spinner.
- Explore shows quiet controls, linked Spatial + UMAP views, shared expression evidence, and Copilot evidence IDs.
- Report leads with Research Brief and 5 evidence-linked findings before methods, limitations, and downloads.

## Remaining limitations

- Streamlit's native top navigation and local `Deploy` button remain visible in development screenshots.
- Full LLM answers depend on local secrets; screenshots were captured in rule/fallback mode.
- Advanced intentionally still contains tool registry, audits, raw state, and extra artifact downloads for provenance.
