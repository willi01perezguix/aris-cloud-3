from __future__ import annotations

import argparse
import json

from aris3_client_sdk import ApiSession, load_config
from aris3_client_sdk.clients.media_client import MediaClient
from aris3_client_sdk.exceptions import ApiError


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve media for a SKU/variant")
    parser.add_argument("--env-file", default=None)
    parser.add_argument("--sku", required=True)
    parser.add_argument("--var1")
    parser.add_argument("--var2")
    args = parser.parse_args()

    config = load_config(args.env_file)
    session = ApiSession(config)
    client = MediaClient(http=session._http(), access_token=session.token)
    try:
        payload = client.resolve_for_variant(args.sku, args.var1, args.var2)
        print(json.dumps(payload.model_dump(mode="json"), indent=2, default=str))
    except ApiError as exc:
        print(json.dumps({"code": exc.code, "message": exc.message, "trace_id": exc.trace_id}, indent=2))
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
