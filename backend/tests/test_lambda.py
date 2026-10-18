"""The Lambda entrypoints work with API Gateway HTTP API (payload v2) events - no AWS account needed."""
import json

from .conftest import login  # noqa: F401  (ensures test env vars are set before app import)


def _event(method, path, body=None, headers=None):
    return {
        "version": "2.0", "routeKey": "$default", "rawPath": path, "rawQueryString": "",
        "headers": {"content-type": "application/json", **(headers or {})},
        "requestContext": {"http": {"method": method, "path": path, "sourceIp": "1.2.3.4", "protocol": "HTTP/1.1"}, "accountId": "x", "stage": "$default"},
        "body": json.dumps(body) if body is not None else None, "isBase64Encoded": False,
    }


def test_api_handler_serves_fastapi_through_mangum(client):
    import lambda_handler

    r = lambda_handler.api_handler(_event("GET", "/api/health"), None)
    assert r["statusCode"] == 200 and json.loads(r["body"])["status"] == "ok"

    r = lambda_handler.api_handler(_event("POST", "/api/auth/login", {"email": "admin@t.io", "password": "password123"}), None)
    assert r["statusCode"] == 200
    token = json.loads(r["body"])["token"]

    r = lambda_handler.api_handler(_event("GET", "/api/dashboard", headers={"authorization": f"Bearer {token}"}), None)
    assert r["statusCode"] == 200 and json.loads(r["body"])["total"] == 0

    r = lambda_handler.api_handler(_event("GET", "/api/dashboard"), None)
    assert r["statusCode"] == 401


def test_scan_handler_reports_counts(client):
    import lambda_handler

    r = lambda_handler.scan_handler({}, None)
    body = json.loads(r["body"])
    assert r["statusCode"] == 200 and body["scanned"] == 0 and body["flagged"] == 0
