# Psychemetre AI — Milestone 2

Milestone 2 hardens the existing Milestone 1 assessment foundation. It preserves the agreed `app/` architecture and the 16-item prototype questionnaire. It introduces explicit transaction ownership in services, report persistence, and an Alembic-managed schema lifecycle.

## Scope and safeguards

- The four classical temperaments are a traditional reflective framework, not validated clinical categories or diagnoses.
- Emotional entries are user self-reports; the system does not infer emotions or diagnose mental-health conditions.
- The 16 sample questions, equal weights (`1.0`), reverse scoring (`6 - response`) and normalisation formula are unchanged. Weights and instrument interpretation remain provisional pending expert review and psychometric validation.
- Authentication, production authorisation, LangGraph orchestration, RAG, and a clinically validated screening workflow are not implemented in this milestone.

## Project structure

Milestone 2 extends the existing modules only. In particular, models remain in `app/models/`, repositories in `app/repositories/`, services in `app/services/`, API routes in `app/api/routes/`, and Alembic revisions in `migrations/versions/`.

## Local setup (SQLite)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

The default database is `sqlite:///./innermap.db`. Apply the schema before starting the API:

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000/docs>.

The API startup hook seeds the versioned sample instrument idempotently. It does **not** create or modify database tables. Schema changes must be applied through Alembic.

## PostgreSQL with Docker Compose

Start PostgreSQL:

```bash
docker compose up -d db
```

For a local host Python environment, set `DATABASE_URL` in `.env` to:

```dotenv
DATABASE_URL=postgresql+psycopg://innermap:change-me@localhost:5432/innermap
APP_ENV=development
```

Apply migrations and run the API:

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

Alternatively, run the API container after the database is ready:

```bash
docker compose run --rm api alembic upgrade head
docker compose up -d api
```

Replace the example database password before using this configuration beyond local development. Production secrets must be supplied through the deployment environment, not committed to source control.

## Alembic workflow

Check the current database revision:

```bash
alembic current
alembic history
```

Create a new revision after changing SQLAlchemy models:

```bash
alembic revision --autogenerate -m "describe schema change"
```

Review the generated migration before applying it. Autogenerate is a draft, not a substitute for human review—especially for renames, data migrations, constraints, and destructive changes.

Apply the latest schema:

```bash
alembic upgrade head
```

Roll back one revision:

```bash
alembic downgrade -1
```

Roll back all revisions (destructive; development/test databases only):

```bash
alembic downgrade base
```

Check that model metadata and the applied schema have no detected drift:

```bash
alembic check
```

For production, back up the database, review the migration SQL, test the upgrade against a staging copy, and plan a recovery path before deploying. Do not casually downgrade a production database after application writes have occurred.

## Tests

```bash
pytest -q
```

The tests use isolated in-memory SQLite databases for service/repository behavior and a temporary SQLite file for migration upgrade/downgrade/schema-drift checks. PostgreSQL URL/driver configuration is checked without requiring a running PostgreSQL server. A real PostgreSQL integration run is still recommended before production deployment.

## API flow

1. `POST /api/v1/assessments/start` with `{"user_id":"demo","instrument_code":"innermap_temperament","instrument_version":"0.1.0"}`.
2. Submit each answer using `POST /api/v1/assessments/{id}/answers` with `{"question_id":1,"value":4}`.
3. Optionally record an emotional self-report using `POST /api/v1/emotions/sessions/{id}`. Emotion, frequency, intensity (0–10), duration, and optional trigger/response/coping/impact are self-reported.
4. Complete using `POST /api/v1/assessments/{id}/complete`. Scores and a versioned report snapshot are persisted atomically.
5. Retrieve the saved report using `GET /api/v1/reports/{report_id}`.

## Persistence and transaction boundaries

Repository functions perform queries, add/update ORM objects, and flush when identifiers or constraint checks are needed. They do not commit. Service functions own commit/rollback boundaries so a multi-row operation (scores, report snapshot, and completed session status) is persisted atomically. The database enforces unique instrument versions, one answer per session/question, one score per session/dimension, and one report per session.

## Research and product work still required

Expert content review; cognitive interviews; pilot testing; reliability and test-retest studies; exploratory/confirmatory factor analysis; convergent/discriminant validity; measurement invariance and cultural adaptation; appropriate licensing/validation for any emotional screening instruments; ethics review, informed consent, privacy controls, access control, and jurisdiction-specific legal review. A high internal-consistency coefficient alone does not establish validity.

## Recommended next milestone

Implement authenticated user ownership and access control for assessment sessions, answers, emotional self-reports, and reports; add a secure session-resume flow and API-level integration tests. Keep agent orchestration and RAG for a later milestone, after persistence, identity, consent, and data-access boundaries are dependable.
