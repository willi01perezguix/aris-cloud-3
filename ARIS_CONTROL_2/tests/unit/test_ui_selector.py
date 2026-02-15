from aris_control_2.app.main import resolve_ui_mode


def test_resolve_ui_mode_defaults_to_gui() -> None:
    assert resolve_ui_mode(None) == "gui"


def test_resolve_ui_mode_accepts_cli() -> None:
    assert resolve_ui_mode("cli") == "cli"


def test_resolve_ui_mode_falls_back_to_gui_for_unknown_values() -> None:
    assert resolve_ui_mode("desktop") == "gui"
