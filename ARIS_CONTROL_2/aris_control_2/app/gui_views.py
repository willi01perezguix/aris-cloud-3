from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import Callable

from aris_control_2.app.gui_controller import LoginResult


class MainWindow:
    def __init__(
        self,
        root: tk.Tk,
        *,
        on_login: Callable[[], None],
        on_diagnostics: Callable[[], None],
        on_support: Callable[[], None],
        on_exit: Callable[[], None],
    ) -> None:
        self.root = root
        root.title("ARIS_CONTROL_2 - GUI v1")
        root.geometry("460x240")
        root.resizable(False, False)

        self.status_value = tk.StringVar(value="No evaluada")
        self.base_url_value = tk.StringVar(value="-")
        self.version_value = tk.StringVar(value="-")

        frame = tk.Frame(root, padx=16, pady=16)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text="Estado de conectividad:", anchor="w").pack(fill="x")
        tk.Label(frame, textvariable=self.status_value, font=("TkDefaultFont", 11, "bold"), anchor="w").pack(fill="x", pady=(0, 8))

        tk.Label(frame, text="Base URL:", anchor="w").pack(fill="x")
        tk.Label(frame, textvariable=self.base_url_value, anchor="w").pack(fill="x", pady=(0, 8))

        tk.Label(frame, text="Versión:", anchor="w").pack(fill="x")
        tk.Label(frame, textvariable=self.version_value, anchor="w").pack(fill="x", pady=(0, 14))

        buttons = tk.Frame(frame)
        buttons.pack(fill="x")
        tk.Button(buttons, text="Login", width=12, command=on_login).pack(side="left", padx=(0, 6))
        tk.Button(buttons, text="Diagnóstico", width=12, command=on_diagnostics).pack(side="left", padx=6)
        tk.Button(buttons, text="Soporte", width=12, command=on_support).pack(side="left", padx=6)
        tk.Button(buttons, text="Salir", width=12, command=on_exit).pack(side="right")

    def set_header(self, *, connectivity: str, base_url: str, version: str) -> None:
        self.status_value.set(connectivity)
        self.base_url_value.set(base_url)
        self.version_value.set(version)


class LoginDialog:
    def __init__(self, root: tk.Tk, on_submit: Callable[[str, str], LoginResult]) -> None:
        self._on_submit = on_submit
        self._dialog = tk.Toplevel(root)
        self._dialog.title("Login")
        self._dialog.transient(root)
        self._dialog.grab_set()
        self._dialog.resizable(False, False)

        frame = tk.Frame(self._dialog, padx=16, pady=16)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text="username_or_email").pack(anchor="w")
        self._username = tk.Entry(frame, width=36)
        self._username.pack(fill="x", pady=(0, 8))

        tk.Label(frame, text="password").pack(anchor="w")
        self._password = tk.Entry(frame, width=36, show="*")
        self._password.pack(fill="x", pady=(0, 8))

        self._error_text = tk.StringVar(value="")
        tk.Label(frame, textvariable=self._error_text, fg="#b00020", justify="left").pack(fill="x", pady=(0, 8))

        tk.Button(frame, text="Ingresar", command=self._submit).pack(anchor="e")
        self._username.focus_set()

    def _submit(self) -> None:
        result = self._on_submit(self._username.get(), self._password.get())
        if result.success:
            messagebox.showinfo("Login", result.message, parent=self._dialog)
            self._dialog.destroy()
            return

        trace_id = result.trace_id or "N/A"
        self._error_text.set(f"{result.message}\ntrace_id: {trace_id}")

    def wait(self) -> None:
        self._dialog.wait_window()
