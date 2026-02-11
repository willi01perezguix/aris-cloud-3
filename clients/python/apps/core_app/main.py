from __future__ import annotations

import logging

from app.bootstrap import CoreAppBootstrap
from app.state import Route


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


def run() -> int:
    bootstrap = CoreAppBootstrap()
    result = bootstrap.start()
    if result.route is Route.LOGIN:
        print("ARIS CORE-3 app shell is ready: login required.")
    elif result.route is Route.CHANGE_PASSWORD:
        print("ARIS CORE-3 app shell is ready: password change required.")
    else:
        print("ARIS CORE-3 app shell loaded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
