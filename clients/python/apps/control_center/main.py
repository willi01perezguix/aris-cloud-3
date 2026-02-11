from __future__ import annotations

from apps.control_center.app.bootstrap import ControlCenterBootstrap


def main() -> None:
    bootstrap = ControlCenterBootstrap()
    # UI shell entrypoint for desktop integration; real Tk wiring handled in ARIS package shell.
    print(f"Control Center initialized for env={bootstrap.config.env_name}")


if __name__ == "__main__":
    main()
