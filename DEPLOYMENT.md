# SpatialScope Deployment

This guide is for the public interactive app. GitHub Pages serves the static
project overview; Streamlit Community Cloud serves the live Agent UI.

## Current URLs

- Static site: https://seu-yolo.github.io/spatialscope-agent/
- GitHub repo: https://github.com/seu-yolo/spatialscope-agent
- Interactive app: https://spatialscope-seu.streamlit.app/

## Streamlit Community Cloud

Use the official Streamlit Community Cloud deploy flow.

Deploy settings:

- Repository: `seu-yolo/spatialscope-agent`
- Branch: `main`
- Main file path: `app.py`
- Python version: `3.11`
- Dependency file: `environment.yml`

The repository intentionally does not add `requirements.txt`. Community Cloud
chooses one dependency file by priority, and `environment.yml` is the project
source of truth for the scientific runtime.

## Secrets

Open the app's Advanced settings and paste the contents of
`.streamlit/secrets.example.toml`, replacing only the API key value.

```toml
SPATIALSCOPE_LLM_PROVIDER = "openai_compatible"
SPATIALSCOPE_LLM_API_KEY = "paste_your_glm_api_key_here"
SPATIALSCOPE_LLM_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
SPATIALSCOPE_LLM_MODEL = "glm-5.1"
SPATIALSCOPE_LLM_TIMEOUT_SECONDS = "10"
SPATIALSCOPE_COPILOT_TIMEOUT_SECONDS = "45"
SPATIALSCOPE_LLM_MODE = "auto"
```

Root-level Streamlit secrets are also exposed as environment variables at
runtime, which matches SpatialScope's LLM configuration layer.

## Data Boundary

Large `.h5ad` and `.tar` files are ignored by Git and should not be committed.
The public app can run the bundled synthetic demo immediately. For real data,
use the local download script or upload an `.h5ad` file through the app:

```bash
scripts/download_real_demo.sh
```

## Post-deploy Check

After the Streamlit app builds:

1. Open the public `*.streamlit.app` URL.
2. Confirm the Project page loads without editing JSON.
3. Run the bundled embryo demo.
4. Ask two different Copilot questions and confirm evidence IDs are shown.
5. Open Explore and confirm Spatial + UMAP views render side by side.
6. Open Report and confirm 3-5 findings, evidence, and caveats are visible.

Then add the Streamlit URL to the top of `README.md` and to the static Pages
site if needed.
