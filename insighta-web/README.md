# Insighta Labs+ Web Portal

Standalone FastAPI and Jinja2 web portal for Insighta Labs+. The portal does not share code or a database with the backend; it talks to the backend with HTTP requests.

## Configuration

Create or edit `.env`:

```env
BACKEND_URL=https://your-backend-url.railway.app
SECRET_KEY=your-random-secret-key-for-csrf
PORT=5000
```

## Install

```bash
pip install -e .
```

## Run

```bash
uvicorn app.main:app --reload --port 5000
```

Open `http://localhost:5000/login`.
