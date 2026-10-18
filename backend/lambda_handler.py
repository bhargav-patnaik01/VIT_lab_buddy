"""AWS Lambda entrypoints.

api_handler   - API Gateway (HTTP API) -> FastAPI app, via Mangum
scan_handler  - EventBridge schedule (daily): the calibration due-date scan, publishes a digest to SNS
"""
import json

from mangum import Mangum

from app.bootstrap import ensure_admin
from app.db import SessionLocal, init_db
from app.main import app
from app.notify import publish
from app.services import due

init_db()  # idempotent CREATE TABLE IF NOT EXISTS on cold start (swap for Alembic once the schema needs migrations)
ensure_admin()  # creates the first administrator on an empty database

api_handler = Mangum(app, lifespan="off")


def scan_handler(event, context):
    with SessionLocal() as db:
        result = due.scan(db)
        flagged = sum(len(v) for v in result["attention"].values())
        if flagged:
            publish(f"Calibration digest: {result['counts'].get('overdue', 0)} overdue, {flagged} need attention", due.digest_text(result))
        return {"statusCode": 200, "body": json.dumps({"scanned": result["scanned"], "counts": result["counts"], "flagged": flagged})}
