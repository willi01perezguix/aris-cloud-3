from __future__ import annotations

import argparse
import json

from aris3_client_sdk import ApiSession, load_config
from aris3_client_sdk.clients.access_control import AccessControlClient
from aris3_client_sdk.clients.auth import AuthClient
from aris3_client_sdk.clients.health import HealthClient
from aris3_client_sdk.exceptions import ApiError


def cmd_login(args: argparse.Namespace) -> None:
    config = load_config(args.env_file)
    session = ApiSession(config)
    auth = AuthClient(http=session._http())
    token = auth.login(args.username, args.password)
    authed = AuthClient(http=session._http(), access_token=token.access_token)
    user = authed.me()
    session.establish(token, user)
    print(json.dumps({"user": user.model_dump(), "trace_id": token.trace_id}, indent=2))


def cmd_me(args: argparse.Namespace) -> None:
    config = load_config(args.env_file)
    session = ApiSession(config)
    auth = AuthClient(http=session._http(), access_token=session.token)
    user = auth.me()
    print(json.dumps(user.model_dump(), indent=2))


def cmd_permissions(args: argparse.Namespace) -> None:
    config = load_config(args.env_file)
    session = ApiSession(config)
    client = AccessControlClient(http=session._http(), access_token=session.token)
    permissions = client.effective_permissions()
    print(json.dumps(permissions.model_dump(), indent=2))


def cmd_health(args: argparse.Namespace) -> None:
    config = load_config(args.env_file)
    session = ApiSession(config)
    client = HealthClient(http=session._http())
    print(json.dumps(client.health(), indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="ARIS3 SDK smoke CLI")
    parser.add_argument("--env-file", default=None)
    subparsers = parser.add_subparsers(dest="command", required=True)

    login_parser = subparsers.add_parser("login")
    login_parser.add_argument("--username", required=True)
    login_parser.add_argument("--password", required=True)
    login_parser.set_defaults(func=cmd_login)

    me_parser = subparsers.add_parser("me")
    me_parser.set_defaults(func=cmd_me)

    perms_parser = subparsers.add_parser("permissions")
    perms_parser.set_defaults(func=cmd_permissions)

    health_parser = subparsers.add_parser("health")
    health_parser.set_defaults(func=cmd_health)

    args = parser.parse_args()
    try:
        args.func(args)
    except ApiError as exc:
        print(json.dumps({"error": exc.code, "message": exc.message, "trace_id": exc.trace_id}, indent=2))
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
