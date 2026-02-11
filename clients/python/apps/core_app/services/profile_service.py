from __future__ import annotations

import logging

from aris3_client_sdk import ApiSession
from aris3_client_sdk.models import UserResponse

logger = logging.getLogger(__name__)


class ProfileService:
    def __init__(self, session: ApiSession) -> None:
        self.session = session

    def load_profile(self) -> UserResponse:
        logger.info("profile_fetch_attempt")
        profile = self.session.auth_client().me()
        logger.info("profile_fetch_success", extra={"trace_id": profile.trace_id, "user_id": profile.id})
        return profile
