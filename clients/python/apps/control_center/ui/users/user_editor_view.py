from __future__ import annotations


def validate_create_user(payload: dict) -> dict[str, str]:
    errors: dict[str, str] = {}
    if not payload.get("username"):
        errors["username"] = "Username is required"
    if not payload.get("email"):
        errors["email"] = "Email is required"
    if not payload.get("password") or len(str(payload.get("password"))) < 8:
        errors["password"] = "Password must be at least 8 characters"
    return errors


def validate_edit_user(payload: dict) -> dict[str, str]:
    errors: dict[str, str] = {}
    if "username" in payload and not payload.get("username"):
        errors["username"] = "Username cannot be empty"
    if "email" in payload and not payload.get("email"):
        errors["email"] = "Email cannot be empty"
    return errors
