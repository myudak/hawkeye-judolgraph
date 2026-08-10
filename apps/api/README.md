# HAWK-EYE API and evidence engine

The Python package lives in `src/hawkeye`. Repository-level dependency, test, lint, and packaging
configuration remains in the root `pyproject.toml` so the CLI and controlled evaluation suite use
one environment.

The API is not a separate public service. In production-like use it serves the generated React
bundle and remains a single-machine investigator application.
