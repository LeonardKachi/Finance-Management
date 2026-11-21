# Imperium Pecuniae

Personal finance site. `index.html` is the whole app. A scheduled GitHub Action refreshes `data.json` (top stocks, bond funds, yields) twice each weekday.

## Publish
1. Upload everything in this folder to a new public repository, keeping the folder structure (`.github/workflows/update-data.yml`, `scripts/update_data.py`, `data.json`, `index.html`).
2. Settings, Pages: deploy from branch `main`, folder `/ (root)`.
3. Settings, Actions, General, Workflow permissions: choose "Read and write permissions".
4. Actions tab, "Update market data", Run workflow. The first run fills `data.json`.

## Change what is ranked
Edit the `STOCKS`, `FUNDS` and `INDICES` lists in `scripts/update_data.py`. Symbols are Yahoo Finance symbols.

## If updates stop
GitHub pauses scheduled workflows after about 60 days without repository activity. Open Actions and re-enable the workflow.
