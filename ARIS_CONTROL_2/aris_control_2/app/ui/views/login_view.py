class LoginView:
    def prompt_credentials(self) -> tuple[str, str]:
        username_or_email = input("username_or_email: ").strip()
        password = input("password: ").strip()
        return username_or_email, password
