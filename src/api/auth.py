"""
Jednostavna autentifikacija za dashboard: jedna deljena lozinka (DASHBOARD_PASSWORD
u .env) -> potpisan token (30 dana vazenja, telefon ostaje ulogovan) koji se
salje kao 'Authorization: Bearer <token>' na svaki API poziv.

Ovo je dovoljno za interni alat za jednog korisnika (vlasnika firme). Ako se
dashboard izlaze na javni internet (a ne kroz VPN kao sto je Tailscale),
obavezno postaviti jaku, nasumicnu DASHBOARD_PASSWORD i DASHBOARD_SECRET_KEY.
"""

from __future__ import annotations

import hmac

from fastapi import Header, HTTPException
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from config import settings

TOKEN_MAX_AGE_SECONDS = 60 * 60 * 24 * 30  # 30 dana


def _serializer() -> URLSafeTimedSerializer:
    if not settings.DASHBOARD_SECRET_KEY:
        raise RuntimeError(
            "DASHBOARD_SECRET_KEY nije podesen u .env. Generisi ga sa: "
            "python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    return URLSafeTimedSerializer(settings.DASHBOARD_SECRET_KEY)


def create_token() -> str:
    return _serializer().dumps({"auth": True})


def verify_password(password: str) -> bool:
    if not settings.DASHBOARD_PASSWORD:
        return False
    return hmac.compare_digest(password, settings.DASHBOARD_PASSWORD)


def require_auth(authorization: str | None = Header(default=None)) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Nedostaje token za prijavu")
    token = authorization.removeprefix("Bearer ")
    try:
        _serializer().loads(token, max_age=TOKEN_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired):
        raise HTTPException(status_code=401, detail="Nevazeci ili istekao token, prijavi se ponovo")
