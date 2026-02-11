from __future__ import annotations

import logging

from aris3_client_sdk import ApiSession
from aris3_client_sdk.exceptions import MustChangePasswordError
from aris3_client_sdk.models import TokenResponse

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self, session: ApiSession) -> None:
        self.session = session

    def has_active_session(self) -> bool:
        return bool(self.session.token)

    def login(self, username: str, password: str) -> TokenResponse:
        logger.info("login_attempt", extra={"username": username})
        try:
            token = self.session.auth_client().login(username, password)
        except MustChangePasswordError:
            logger.warning("login_requires_password_change", extra={"username": username})
            raise
        except Exception:
            logger.exception("login_failure", extra={"username": username})
            raise
        logger.info("login_success", extra={"username": username, "trace_id": token.trace_id})
        return token

    def change_password(self, current_password: str, new_password: str, idempotency_key: str) -> TokenResponse:
        logger.info("change_password_attempt")
        token = self.session.auth_client().change_password(
            current_password=current_password,
            new_password=new_password,
            idempotency_key=idempotency_key,
        )
        logger.info("change_password_success", extra={"trace_id": token.trace_id})
        return token

    def logout(self) -> None:
        logger.info("logout")
        self.session.logout()
