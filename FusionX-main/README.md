# FusionX

## Run Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

This backend bridges to `../project/main.py` and exposes:

- `GET /health`
- `GET /dataset-status`
- `POST /analyze-text`
- `POST /encode-image`

## Run Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend default API target is `http://localhost:8000`.  
To override, set `VITE_API_BASE` before running `npm run dev`.
