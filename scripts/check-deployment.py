"""Read-only hosted smoke checks. No credentials, records or employer actions."""

import argparse
import sys
from urllib.parse import urlsplit

import httpx


def check(url):
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
    ):
        raise ValueError("Use the final HTTPS frontend origin without a path or credentials")
    with httpx.Client(base_url=url.rstrip("/"), timeout=40, follow_redirects=False) as client:
        assert client.get("/").status_code == 200, "Frontend page unavailable"
        ready = client.get("/api/ready")
        assert ready.status_code == 200, "API not ready; allow a cold start, then retry"
        assert ready.headers.get("cache-control") == "no-store", "API response must not be cached"
        assert client.get("/api/auth/me").status_code == 401, "Account endpoint must require login"
        rejected = client.post(
            "/api/auth/logout", headers={"origin": "https://untrusted.example"}, json={}
        )
        assert rejected.status_code == 403, "Cross-origin mutation was not rejected"
    print(
        "Hosted page, API readiness, private account access, origin check and no-cache headers passed."
    )
    print("Now verify signed-in behavior, worker execution and email delivery on the actual hosts.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    args = parser.parse_args()
    try:
        check(args.url)
    except (AssertionError, ValueError, httpx.HTTPError) as exc:
        print(f"Hosted smoke check failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
