from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow


DEFAULT_SCOPES: tuple[str, ...] = (
    "https://www.googleapis.com/auth/calendar",
)


@dataclass(frozen=True)
class AuthConfig:
    client_secret_path: Path
    token_path: Path
    scopes: tuple[str, ...] = DEFAULT_SCOPES


class AuthError(RuntimeError):
    pass


def _default_token_path() -> Path:
    xdg_config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return xdg_config_home / "google_calendar_mcp" / "token.json"


def load_auth_config() -> AuthConfig:
    raw = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET_PATH", "").strip()
    if not raw:
        raise AuthError(
            "Missing env GOOGLE_OAUTH_CLIENT_SECRET_PATH pointing to your OAuth client_secret JSON."
        )

    client_secret_path = Path(raw).expanduser().resolve()
    if not client_secret_path.exists():
        raise AuthError(f"OAuth client_secret file not found: {client_secret_path}")

    token_path = Path(
        os.environ.get("GOOGLE_OAUTH_TOKEN_PATH", str(_default_token_path()))
    ).expanduser()

    scopes_env = os.environ.get("GOOGLE_OAUTH_SCOPES", "").strip()
    scopes = tuple(s.strip() for s in scopes_env.split(",") if s.strip()) or DEFAULT_SCOPES

    return AuthConfig(
        client_secret_path=client_secret_path,
        token_path=token_path,
        scopes=scopes,
    )


def _read_token_file(token_path: Path) -> Optional[dict]:
    try:
        return json.loads(token_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except Exception as e:  # pragma: no cover
        raise AuthError(f"Failed reading token file at {token_path}: {e}") from e


def _write_token_file(token_path: Path, data: dict) -> None:
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def get_credentials(*, scopes: Iterable[str] | None = None) -> Credentials:
    cfg = load_auth_config()
    scopes_tuple = tuple(scopes) if scopes is not None else cfg.scopes

    token_data = _read_token_file(cfg.token_path)
    creds: Optional[Credentials] = None
    if token_data:
        creds = Credentials.from_authorized_user_info(token_data, scopes=scopes_tuple)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _write_token_file(cfg.token_path, json.loads(creds.to_json()))
        return creds

    if creds and creds.valid:
        return creds

    flow = InstalledAppFlow.from_client_secrets_file(
        str(cfg.client_secret_path), scopes=scopes_tuple
    )

    # Uses local server flow by default; opens a browser and listens on localhost.
    # Your client_secret includes redirect_uris=["http://localhost"], which works here.
    creds = flow.run_local_server(
        host="localhost",
        port=0,
        authorization_prompt_message="Please visit this URL to authorize this application: {url}",
        success_message="Authorization complete. You may close this window.",
        open_browser=True,
    )
    _write_token_file(cfg.token_path, json.loads(creds.to_json()))
    return creds

