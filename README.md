# OI Gamma

Streamlit app showing GEX / VEX heatmaps for US stocks and indices, using CBOE delayed option data (~15 min).

## Run locally
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# create .streamlit/secrets.toml with:
#   APP_PASSWORD = "your-password"
#   DATABASE_URL = "postgresql://..."   (optional: Neon; without it -> local data/history.db)
streamlit run app.py
```

## History DB
Daily snapshots (for the % badges) and the watchlist live in Neon Postgres when `DATABASE_URL` is set.
One-off copy of local SQLite history into Neon: `python -m scripts.copy_history`

## Tests
```powershell
pytest
```
