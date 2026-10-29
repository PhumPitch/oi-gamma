# OI Gamma

Streamlit app showing GEX / VEX heatmaps for US stocks and indices, using CBOE delayed option data (~15 min).

## Run locally
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# create .streamlit/secrets.toml with: APP_PASSWORD = "your-password"
streamlit run app.py
```

## Tests
```powershell
pytest
```
