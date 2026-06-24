# Security Policy

SpatialScope Agent is a course research project that may process biological
datasets and connect to an OpenAI-compatible LLM provider.

## Supported Version

The `main` branch is the supported development line for the current course
submission.

## Secret Handling

- Do not commit `.env`, `.streamlit/secrets.toml`, API keys, tokens, or private
  datasets.
- Configure deployed LLM keys through Streamlit Community Cloud Secrets.
- The LLM layer must not receive raw expression matrices or raw coordinate
  matrices. It should only receive dataset summaries, tool summaries, evidence
  IDs, caveats, and metadata.

## Reporting Issues

Open a GitHub issue for reproducible bugs that do not contain secrets or private
data. For sensitive reports, contact the repository owner privately instead of
posting public logs.

Please include:

- app path or CLI command
- dataset shape and whether spatial coordinates exist
- run mode
- relevant warning/error excerpt with secrets removed

