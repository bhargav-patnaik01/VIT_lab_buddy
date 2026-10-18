# Lab Calibration & Access Tracker (VIT)

Cloud-based tracker for lab-equipment calibration, certificates, usage and lab access — built from the project
review in `Cloud_presentation_MVP_4services.docx`. First customer: VIT's laboratories.

## Run it locally

```powershell
.\scripts\run-local.ps1          # creates venv, builds UI, seeds demo data on first run, starts http://127.0.0.1:8000
.\scripts\run-local.ps1 -Reset   # wipe and re-seed the demo data
```

Needs Python 3.11+ and Node 20+. No AWS account, Docker or database server required locally
(SQLite + local disk stand in for RDS + S3).

Demo logins (password `Vit@2026`): `admin@vit.ac.in`, `head@vit.ac.in`, `electronics@vit.ac.in`,
`mechanical@vit.ac.in`, `chemistry@vit.ac.in`, `physics@vit.ac.in`, `biotech@vit.ac.in`.
The demo-account buttons on the sign-in page only appear on `localhost`.

UI hot-reload while developing: `cd backend; .\.venv\Scripts\python -m uvicorn app.main:app --reload` and
`cd frontend; npm run dev` (http://localhost:5173, proxies `/api` to :8000).

Tests: `cd backend; .\.venv\Scripts\python -m pytest` (26 tests: due-date logic, department isolation,
audit chain, uploads, device ingest, Lambda entrypoints).

## What it does

| Area | Behaviour |
|---|---|
| Instruments | Register per department; calibrate by **time interval**, **hours of use**, or **whichever comes first** |
| Calibration | Record result (pass / adjusted / fail), upload certificate (PDF/PNG/JPG ≤ 5 MB, SHA-256 stored) |
| Status | Calibrated · Due soon (30 days / last 10 % of hours) · Overdue · Failed · Not calibrated · Out of service |
| Usage | Start/stop sessions, manual logs, or device events; hours since last calibration drive usage-based due dates |
| Lab access | RFID entry/exit events, who is inside each lab now, entries today |
| Audit trail | Every change is in an append-only SHA-256 hash chain; **Verify integrity** finds the first tampered row |
| Reports | CSV exports (instrument status, calibration records) for NBA/NAAC reviews |
| Due-date scan | Daily scheduled job emails the overdue/due-soon digest (SNS on AWS, log output locally) |

### Roles (enforced server-side in `app/policy.py`)

| Role | Sees | Can change |
|---|---|---|
| Administrator | all departments | everything, incl. users and departments |
| Department head | all departments | nothing (read-only) |
| Lab in-charge | own department only | own department's instruments, calibrations, usage, lab access |

Another department's records answer **404** (indistinguishable from "doesn't exist").

## How it maps to AWS (the four services in the report)

| Problem | Service | Where |
|---|---|---|
| Cross-department access control | **IAM** roles, least-privilege per function (+ app-level policy mirroring it) | `infra/template.yaml`, `backend/app/policy.py` |
| Single source of truth | **RDS PostgreSQL 17** (private subnet, encrypted, SG only open to the Lambdas) | `Database` |
| Automated due-date logic | **Lambda** — API (FastAPI via Mangum) + daily scan on EventBridge | `backend/lambda_handler.py` |
| Audit-ready certificate store | **S3** (private, versioned, SSE, TLS-only, presigned downloads) | `CertificateBucket` |
| Plus | CloudFront + S3 (UI, `/api/*` routed to API Gateway same-origin), SNS, Secrets Manager | |

The code is environment-driven, so the same app runs both places: `DATABASE_URL`/`DB_SECRET_ARN`,
`STORAGE_BACKEND=local|s3`, `SNS_TOPIC_ARN`, `JWT_SECRET[_ARN]`, `DEVICE_API_KEY` (see `backend/app/config.py`).

### Deploying (not yet exercised against a real AWS account)

Prerequisites: AWS CLI + SAM CLI + Docker, a VPC with ≥ 2 private subnets that can reach Secrets Manager / SNS / S3
(NAT or VPC endpoints).

```powershell
.\scripts\build-lambda.ps1
cd infra
sam validate --lint
sam build --use-container          # Linux wheels for pydantic-core
sam deploy --guided                # asks for VpcId, PrivateSubnetIds, AlertEmail, DeviceApiKey
cd ..
.\scripts\deploy-frontend.ps1 -StackName <your-stack>
```

First admin: the stack creates `BootstrapAdminSecret` (email = `AlertEmail`); read its password from Secrets
Manager once, sign in, then change it under *Users & departments*. No demo data is ever loaded on AWS.
Confirm the SNS subscription email so the daily digest reaches you.

## Connecting RFID readers / instrument controllers

```bash
curl -X POST https://<site>/api/ingest/access -H "X-Device-Key: <key>" -H "Content-Type: application/json" \
     -d '{"dept_code":"ELE","person_ref":"23BEC1001","direction":"in","card_uid":"04:A1:B2:C3"}'
curl -X POST https://<site>/api/ingest/usage  -H "X-Device-Key: <key>" -H "Content-Type: application/json" \
     -d '{"asset_tag":"VIT-ELE-001","event":"start","user_ref":"23BEC1001"}'      # later: "event":"stop"
```

Local key: `dev-device-key`. API reference: `/api/docs`.

## Layout

```
backend/    FastAPI app (app/), Lambda entrypoints, seed.py, tests/
frontend/   React + Vite UI (VIT logo in public/vit-logo.png)
infra/      SAM / CloudFormation template
scripts/    run-local, build-lambda, deploy-frontend
```

## Known limitations / next steps

- `infra/template.yaml` passes `cfn-lint` but has not been deployed; expect small fixes on first `sam deploy`.
- Tables are created with `create_all` on cold start; add Alembic migrations before the schema changes in production.
- Authentication is app-managed (scrypt + JWT). For VIT rollout, swap in Cognito / the campus SSO.
- Certificates upload through the API (5 MB cap for Lambda/API Gateway payload limits); larger files would need S3 presigned POST.
- A single shared device key authenticates all readers; per-device keys are a straightforward extension.
- Logo is the header image from vit.ac.in — confirm VIT's branding permission before external use.
