# EU-AI

Next.js frontend and FastAPI adapter for the Eastern University RAG assistant.
The FastAPI and Streamlit frontends share a Groq chat model, local multilingual
Hugging Face embeddings, and a Chroma vector index. The multilingual embedding
model loads in half precision to reduce query-time memory use on Render's free
instance.

## Free deployment on Vercel and Render

Deploy the Next.js frontend to Vercel with the project root set to
`varsity-rag-bot/frontend`. Set `BACKEND_URL` in the Vercel project to the
public URL of the API service (for example, `https://eu-ai-api.onrender.com`).
The frontend proxies `/api/*` requests to this service.

Deploy the FastAPI service from the repository-root `render.yaml` as a Render
Blueprint, and provide the `GROQ_API_KEY` secret when prompted. The free API
service uses temporary SQLite storage instead of managed PostgreSQL.

Render's free service may sleep when idle, has limited memory, and has an
ephemeral filesystem. User accounts, chat history, uploaded documents, and
admin index changes can be lost on restart or redeploy. The checked-in Chroma
index is available after each deployment; uploaded files and re-indexing
changes are not durable. The initial administrator must be created again if
the SQLite database is reset.

## Run locally on Windows

Install the API dependencies from the project folder:

```powershell
.\venv\Scripts\python.exe -m pip install -r .\backend\requirements.txt
```

The API reads `GROQ_API_KEY` from `root\.env` or `backend\.env`. Copy
`backend\.env.example` to `backend\.env` and configure the database URL and JWT
secret there. Generate a JWT secret with:

```powershell
.\venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

Set `DATABASE_URL` to a PostgreSQL async URL such as
`postgresql+asyncpg://<user>:<password>@<host>:5432/<database>`, and set the
generated value as `SECRET_KEY`. Never commit `backend\.env` or share the
generated secret. SQLite can be used for local-only development with
`sqlite+aiosqlite:///./eu_ai.db`.

Apply the schema before starting the API:

```powershell
.\venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini upgrade head
```

Students register with a unique student ID, email, full name, and password.
Students sign in with their student ID; administrators can sign in with their
email. All public registrations receive the `student` role; the API rejects a
client-supplied role. Bootstrap the first administrator from a secure terminal
after setting up the database (the bootstrap account also requires a unique
student ID):

```powershell
.\venv\Scripts\python.exe -m backend.app.cli --email admin@example.edu --full-name "EU Administrator" --student-id EU-ADMIN-001
```

The CLI prompts for the password without echoing it. Passwords must be 12–72
UTF-8 bytes. The login screen keeps bearer tokens only in in-memory application
state, so reloading the page requires signing in again. Chat requests require
authentication and successful exchanges are associated with the user's UUID
in `chat_logs`. Every route registered under `/api/v1/admin` is guarded by the
admin role. The admin panel at `/admin` provides system and database counts,
lists source documents, accepts PDF/Markdown/text uploads up to 20 MiB, deletes
admin-uploaded documents, and re-indexes the knowledge base. Uploaded files are
stored under `data/raw/uploaded/`; indexing uses local Hugging Face embeddings
and removes stale vectors for deleted or changed documents. The first indexing
run downloads the multilingual embedding model. Documents
already in `root/university_docs/` or `data/raw/scraped/` are listed and
re-indexed but cannot be deleted from the admin panel.

Build the local embedding index once before asking questions:

```powershell
.\venv\Scripts\python.exe .\root\ingest.py
```

Set `GROQ_API_KEY` in `root\.env` or `backend\.env`; Groq is used only for chat
generation, so document embeddings do not require a Google API key.

Start the API in one PowerShell window:

```powershell
.\venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Install and start the Next.js app in a second window:

```powershell
Set-Location .\frontend
npm install
npm run dev
```

The frontend uses `frontend\.env.local` to reach `http://localhost:8000/api/v1`.
If that file is missing, copy `frontend\.env.local.example` to
`frontend\.env.local`.

Open <http://localhost:3000>. The existing Streamlit interface can continue to
run separately at <http://localhost:8501>.
