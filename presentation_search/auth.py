from __future__ import annotations

from hmac import compare_digest
from ipaddress import ip_address
from uuid import UUID

import jwt
from fastapi import Header, HTTPException, Request

from .config import Settings


def key_matches(supplied: str, expected: str) -> bool:
    return bool(expected.strip()) and compare_digest(supplied.encode(), expected.encode())


def _loopback(host: str | None) -> bool:
    if host == "localhost":
        return True
    try:
        return ip_address(host or "").is_loopback
    except ValueError:
        return False


class Identity:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.roles = {role.strip() for role in settings.entra_allowed_roles.split(",") if role.strip()}
        self.groups = {group.strip() for group in settings.entra_allowed_groups.split(",") if group.strip()}
        self.keys = None
        self.issuer = ""

    def validate(self):
        s = self.settings
        if s.auth_mode == "api_key" and not s.copilot_api_key.strip():
            raise ValueError("COPILOT_API_KEY must be configured for api_key mode")
        if s.admin_api_key.strip() and key_matches(s.admin_api_key, s.copilot_api_key):
            raise ValueError("ADMIN_API_KEY must be distinct from COPILOT_API_KEY")
        if s.auth_mode == "local_demo" and s.knowledge_provider != "local":
            raise ValueError("Local demo requires the local provider")
        if s.auth_mode == "entra":
            tenant = str(UUID(s.azure_tenant_id))
            if not s.entra_audience.strip() or not (self.roles or self.groups):
                raise ValueError("Entra mode requires ENTRA_AUDIENCE and an allowed role or group")
            self.issuer = f"https://login.microsoftonline.com/{tenant}/v2.0"
            self.keys = jwt.PyJWKClient(
                f"https://login.microsoftonline.com/{tenant}/discovery/v2.0/keys", timeout=8
            )

    def principal(
        self, request: Request, x_api_key: str = Header(default=""), authorization: str = Header(default="")
    ) -> str:
        if self.settings.auth_mode == "local_demo":
            if (
                not request.client
                or not _loopback(request.client.host)
                or not _loopback(request.url.hostname)
            ):
                raise HTTPException(403, "The local demo requires a loopback connection")
            return "local_demo"
        if self.settings.auth_mode == "api_key":
            if not key_matches(x_api_key, self.settings.copilot_api_key):
                raise HTTPException(401, "Invalid API key")
            return "shared_api_key"
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token or len(token) > 65536 or self.keys is None:
            raise HTTPException(401, "A valid Entra access token is required")
        try:
            if jwt.get_unverified_header(token).get("alg") != "RS256":
                raise jwt.InvalidTokenError()
            key = self.keys.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                key.key,
                algorithms=["RS256"],
                audience=self.settings.entra_audience,
                issuer=self.issuer,
                options={"require": ["exp", "iat", "iss", "aud", "tid", "oid"]},
            )
            if (
                claims["tid"].lower() != self.settings.azure_tenant_id.lower()
                or not isinstance(claims["oid"], str)
                or not claims["oid"]
            ):
                raise jwt.InvalidTokenError()
        except jwt.PyJWKClientConnectionError:
            raise HTTPException(503, "Tenant signing keys are temporarily unavailable") from None
        except (jwt.PyJWTError, ValueError, TypeError, AttributeError):
            raise HTTPException(401, "Invalid Entra access token") from None
        scopes = claims.get("scp")
        roles, groups = claims.get("roles", []), claims.get("groups", [])
        if not isinstance(scopes, str) or "access_as_user" not in scopes.split():
            raise HTTPException(403, "The delegated access_as_user scope is required")
        if not (
            isinstance(roles, list)
            and any(r in self.roles for r in roles if isinstance(r, str))
            or isinstance(groups, list)
            and any(g in self.groups for g in groups if isinstance(g, str))
        ):
            raise HTTPException(403, "The shared library requires an assigned role or group")
        return f"entra:{claims['tid']}:{claims['oid']}"
