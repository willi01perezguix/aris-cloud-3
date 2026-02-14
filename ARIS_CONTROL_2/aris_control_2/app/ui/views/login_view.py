class LoginView:
    def prompt_credentials(self) -> tuple[str, str]:
        username_or_email = input("username_or_email: ").strip()
        password = input("password: ").strip()
        return username_or_email, password

    def must_change_password_block(self) -> None:
        print("Debes cambiar tu contraseña antes de continuar (must_change_password=true).")
