"""Single-owner OAuth authorization service for the Earnings Graphic Studio MCP.

Dedicated, stateless signed tokens with PKCE-S256 and constrained dynamic client
registration. A long random MCP_OWNER_ACCESS_CODE (falling back to an existing
MCP_BEARER_TOKEN for a migration) is entered ONLY at the hosted /authorize page.
No financial or GitHub account data is involved. This deployment is intended for
an individual owner, not as a general-purpose multi-user identity provider.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import os
import re
import secrets
import time
from collections import deque
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

router = APIRouter()
BASE = os.getenv("MCP_PUBLIC_BASE_URL", "https://earnings-graphic-studio.onrender.com").rstrip("/")
RESOURCE = BASE + "/mcp"
# ChatGPT clients have used both the root service URL and the MCP path as
# the OAuth resource indicator. Both point to this same dedicated service.
ALLOWED_RESOURCES = frozenset((BASE, RESOURCE))
SCOPE = "earnings:render"

# A single replica/worker is used on Render Free. This set is a defense against
# authorisation-code replay within the running worker; PKCE and short expiry
# provide further protections if the Free instance restarts.
CONSUMED: dict[str, float] = {}
ATTEMPTS: dict[str, deque[float]] = {}


def signing_key() -> bytes:
    password = os.getenv("MCP_OWNER_ACCESS_CODE") or os.getenv("MCP_BEARER_TOKEN")
    if not password or len(password) < 32:
        raise RuntimeError("Owner access code must be at least 32 characters")
    return hmac.new(password.encode(), b"earnings-studio/oauth-signing-v1", hashlib.sha256).digest()


def access_password() -> str:
    password = os.getenv("MCP_OWNER_ACCESS_CODE") or os.getenv("MCP_BEARER_TOKEN")
    if not password or len(password) < 32:
        raise RuntimeError("Owner access code must be at least 32 characters")
    return password


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def unb64(v: str) -> bytes:
    return base64.urlsafe_b64decode(v + "=" * (-len(v) % 4))


def sign(data: dict[str, Any]) -> str:
    payload = b64url(json.dumps(data, separators=(",", ":"), sort_keys=True).encode())
    sig = b64url(hmac.new(signing_key(), payload.encode("ascii"), hashlib.sha256).digest())
    return payload + "." + sig


def verify(encoded: str, kind: str) -> dict[str, Any]:
    try:
        body, mac = encoded.split(".", 1)
        expected = b64url(hmac.new(signing_key(), body.encode("ascii"), hashlib.sha256).digest())
        if not hmac.compare_digest(mac, expected):
            raise ValueError("signature")
        payload = json.loads(unb64(body))
        now = time.time()
        if not isinstance(payload, dict) or payload.get("kind") != kind or not isinstance(payload.get("exp"), (int, float)) or payload["exp"] <= now:
            raise ValueError("expired or incorrect token")
        return payload
    except (ValueError, TypeError, KeyError, json.JSONDecodeError, UnicodeError) as exc:
        raise ValueError("Invalid or expired credential") from exc


def redirect_allowed(url: str) -> bool:
    try:
        p = urlsplit(url)
        if p.scheme != "https" or p.netloc != "chatgpt.com" or p.username or p.password or p.query or p.fragment:
            return False
        if p.path == "/connector_platform_oauth_redirect":
            return True
        return bool(re.fullmatch(r"/connector/oauth/[A-Za-z0-9_-]{8,200}", p.path))
    except ValueError:
        return False


def from_form(raw: bytes) -> dict[str, str]:
    if len(raw) > 8192:
        raise HTTPException(status_code=413, detail="Form is too large")
    try:
        values = parse_qs(raw.decode("utf-8"), strict_parsing=True, keep_blank_values=True, max_num_fields=20)
        return {key: val[-1] for key, val in values.items()}
    except (ValueError, UnicodeError):
        raise HTTPException(status_code=400, detail="Malformed form")


def fail_json(error: str, status: int = 400) -> JSONResponse:
    return JSONResponse({"error": error}, status_code=status, headers={"Cache-Control": "no-store"})


def safe_page(ctx: str, warning: str = "") -> HTMLResponse:
    # The user supplies the long Render owner access code in the hosted browser,
    # never to a chat prompt. No JS, third-party assets, or analytics.
    ctx_html = html.escape(ctx, quote=True)
    message = '<p class="err">Invalid owner access code. Please try again.</p>' if warning else ""
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Connect Earnings Graphic Studio</title><style>
body{{margin:0;background:#f2f5f9;color:#142a45;font:16px system-ui,-apple-system,sans-serif}}
main{{max-width:420px;background:white;margin:12vh auto;padding:32px;border-radius:16px;box-shadow:0 10px 35px #12223b20}}
h1{{font-size:24px;margin-top:0}}label{{font-size:14px;display:block;margin:20px 0 8px}}input{{box-sizing:border-box;width:100%;padding:14px;border:1px solid #aab5c2;border-radius:8px;font-size:16px}}
button{{width:100%;padding:13px;margin-top:18px;background:#1e62be;color:white;border:0;border-radius:8px;font-size:16px;cursor:pointer}}
p{{line-height:1.5;font-size:14px;color:#4b5a6a}}.err{{color:#a91520;font-weight:600}}</style></head>
<body><main><h1>Earnings Graphic Studio</h1><p>Authorize your private Sankey renderer to work with ChatGPT. Enter the owner's access code stored in Render's Environment settings under <strong>MCP_BEARER_TOKEN</strong> (or MCP_OWNER_ACCESS_CODE if configured).</p>
{message}<form action="/authorize" method="post"><input type="hidden" name="ctx" value="{ctx_html}">
<label for="access">Owner access code</label><input id="access" name="access" type="password" autocomplete="off" required minlength="32" autofocus>
<button type="submit">Authorize ChatGPT</button></form><p>The code stays between your browser and this Render service. It is not sent to ChatGPT.</p></main></body></html>"""
    return HTMLResponse(page, headers={"Cache-Control": "no-store", "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer"})


def auth_context(q: dict[str, str]) -> dict[str, Any]:
    client_id = q.get("client_id", "")
    try:
        client = verify(client_id, "client")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Unregistered OAuth client") from exc
    redirect = q.get("redirect_uri", "")
    challenge = q.get("code_challenge", "")
    if not redirect_allowed(redirect) or redirect not in client["redirects"]:
        raise HTTPException(status_code=400, detail="Redirect URI not registered")
    if q.get("response_type") != "code" or q.get("code_challenge_method") != "S256" or not re.fullmatch(r"[A-Za-z0-9_-]{43,128}", challenge):
        raise HTTPException(status_code=400, detail="OAuth authorization requires S256 PKCE")
    resource = q.get("resource", RESOURCE)
    if resource not in ALLOWED_RESOURCES:
        raise HTTPException(status_code=400, detail="Wrong protected resource")
    scope = q.get("scope", SCOPE)
    if scope != SCOPE:
        raise HTTPException(status_code=400, detail="Unsupported scope")
    if len(q.get("state", "")) > 1024:
        raise HTTPException(status_code=400, detail="Invalid state length")
    return {"kind": "context", "client_id": client_id, "redirect": redirect, "challenge": challenge, "state": q.get("state", ""), "resource": resource, "scope": scope, "exp": int(time.time() + 600), "nonce": secrets.token_urlsafe(16)}


def minted_tokens(client_id: str, resource: str = RESOURCE) -> dict[str, Any]:
    now = int(time.time())
    return {
        "access_token": sign({"kind": "access", "client_id": client_id, "aud": resource, "scope": SCOPE, "iat": now, "exp": now + 3600}),
        "refresh_token": sign({"kind": "refresh", "client_id": client_id, "aud": resource, "scope": SCOPE, "iat": now, "exp": now + 30 * 86400}),
        "token_type": "Bearer", "expires_in": 3600, "scope": SCOPE,
    }


def validate_access_token(raw: str | None) -> bool:
    if not raw or not raw.startswith("Bearer ") or len(raw) > 5000:
        return False
    try:
        t = verify(raw[7:], "access")
        return t["aud"] in ALLOWED_RESOURCES and t["scope"] == SCOPE and isinstance(t["client_id"], str) and bool(t["client_id"])
    except (ValueError, KeyError):
        return False


@router.get("/.well-known/oauth-protected-resource")
@router.get("/.well-known/oauth-protected-resource/mcp")
def protected_resource_metadata():
    return {"resource": RESOURCE, "authorization_servers": [BASE], "scopes_supported": [SCOPE]}


@router.get("/.well-known/oauth-authorization-server")
def authorization_server_metadata():
    return {
        "issuer": BASE,
        "authorization_endpoint": BASE + "/authorize",
        "token_endpoint": BASE + "/token",
        "registration_endpoint": BASE + "/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "token_endpoint_auth_methods_supported": ["none"],
        "code_challenge_methods_supported": ["S256"],
        "authorization_response_iss_parameter_supported": True,
        "scopes_supported": [SCOPE],
    }


@router.post("/register")
async def register(request: Request):
    raw = await request.body()
    if len(raw) > 8192:
        return fail_json("invalid_client_metadata")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return fail_json("invalid_client_metadata")
    if not isinstance(data, dict):
        return fail_json("invalid_client_metadata")
    redirects = data.get("redirect_uris")
    if not isinstance(redirects, list) or not 1 <= len(redirects) <= 5 or not all(isinstance(x, str) and redirect_allowed(x) for x in redirects):
        return fail_json("invalid_redirect_uri")
    if data.get("token_endpoint_auth_method", "none") != "none":
        return fail_json("invalid_client_metadata")
    issued = int(time.time())
    client_id = sign({"kind": "client", "redirects": sorted(set(redirects)), "iat": issued, "exp": issued + 365 * 86400, "nonce": secrets.token_urlsafe(16)})
    return JSONResponse({"client_id": client_id, "client_id_issued_at": issued, "redirect_uris": redirects,
                         "grant_types": ["authorization_code", "refresh_token"], "response_types": ["code"],
                         "token_endpoint_auth_method": "none", "scope": SCOPE}, status_code=201, headers={"Cache-Control": "no-store"})


@router.get("/authorize")
def authorize(request: Request):
    ctx = sign(auth_context(dict(request.query_params)))
    return safe_page(ctx)


@router.post("/authorize")
async def authorize_post(request: Request):
    form = from_form(await request.body())
    ctx_value = form.get("ctx", "")
    if len(ctx_value) > 5000:
        raise HTTPException(status_code=400, detail="Invalid authorization context")
    try:
        ctx = verify(ctx_value, "context")
    except ValueError:
        raise HTTPException(status_code=400, detail="Authorization session expired")
    # Never log password or query string; attempts limited per originating IP.
    address = request.client.host if request.client else "unknown"
    now = time.time()
    history = ATTEMPTS.setdefault(address, deque())
    while history and history[0] < now - 300:
        history.popleft()
    if len(history) >= 10:
        raise HTTPException(status_code=429, detail="Too many login attempts")
    history.append(now)
    if not hmac.compare_digest(form.get("access", ""), access_password()):
        return safe_page(ctx_value, "incorrect")
    code = sign({"kind": "code", "client_id": ctx["client_id"], "redirect": ctx["redirect"], "challenge": ctx["challenge"],
                 "resource": ctx["resource"], "scope": ctx["scope"], "jti": secrets.token_urlsafe(18), "exp": int(time.time() + 120)})
    parsed = urlsplit(ctx["redirect"])
    query = urlencode({"code": code, "state": ctx["state"], "iss": BASE})
    return RedirectResponse(urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, "")), status_code=303, headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})


@router.post("/token")
async def token_endpoint(request: Request):
    values = from_form(await request.body())
    grant = values.get("grant_type")
    if grant == "authorization_code":
        code = values.get("code", "")
        verifier = values.get("code_verifier", "")
        if not re.fullmatch(r"[A-Za-z0-9._~-]{43,128}", verifier):
            return fail_json("invalid_grant")
        try:
            data = verify(code, "code")
        except ValueError:
            return fail_json("invalid_grant")
        if values.get("client_id") != data["client_id"] or values.get("redirect_uri") != data["redirect"] or values.get("resource", data["resource"]) != data["resource"]:
            return fail_json("invalid_grant")
        sha = b64url(hashlib.sha256(verifier.encode()).digest())
        if not hmac.compare_digest(sha, data["challenge"]):
            return fail_json("invalid_grant")
        ident = data["jti"]
        current = time.time()
        for k, exp in list(CONSUMED.items()):
            if exp < current:
                del CONSUMED[k]
        if ident in CONSUMED:
            return fail_json("invalid_grant")
        CONSUMED[ident] = current + 300
        return JSONResponse(minted_tokens(data["client_id"], data["resource"]), headers={"Cache-Control": "no-store", "Pragma": "no-cache"})
    if grant == "refresh_token":
        try:
            data = verify(values.get("refresh_token", ""), "refresh")
            if values.get("client_id") != data["client_id"] or values.get("resource", data["aud"]) != data["aud"]:
                return fail_json("invalid_grant")
        except ValueError:
            return fail_json("invalid_grant")
        return JSONResponse(minted_tokens(data["client_id"], data["aud"]), headers={"Cache-Control": "no-store", "Pragma": "no-cache"})
    return fail_json("unsupported_grant_type")
