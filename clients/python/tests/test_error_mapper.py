from __future__ import annotations

from aris3_client_sdk.error_mapper import map_error
from aris3_client_sdk.exceptions import ForbiddenError, UnauthorizedError, ValidationError


def test_error_mapper_classes() -> None:
    err = map_error(401, {"code": "INVALID_TOKEN", "message": "bad"}, "trace")
    assert isinstance(err, UnauthorizedError)
    err = map_error(403, {"code": "PERMISSION_DENIED", "message": "no"}, "trace")
    assert isinstance(err, ForbiddenError)
    err = map_error(400, {"code": "VALIDATION_ERROR", "message": "bad"}, "trace")
    assert isinstance(err, ValidationError)
