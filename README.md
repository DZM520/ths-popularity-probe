# ths-popularity-probe

This repo is for probing historical archives and candidate 10jqka/同花顺 hot-rank API endpoints for the given page and nearby ranking URLs.

## Files
- `probe.py` — probes Wayback, archive.today, and candidate API endpoints.
- `.github/workflows/probe.yml` — GitHub Actions workflow to run the probe on demand.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install requests
python probe.py
```

The script will create a `results/` directory with JSON logs and a report file.
