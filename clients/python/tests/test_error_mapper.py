from __future__ import annotations

from aris3_client_sdk.error_mapper import map_error
from aris3_client_sdk.exceptions import ForbiddenError, UnauthorizedError, ValidationError


def test_error_mapper_classes() -> None:
    err = map_error(401, {"code": "INVALID_TOKEN", "message": "bad"}, "trace")
    assert isinstance(err, UnauthorizedError)
    assert err.trace_id == "trace"
    err = map_error(403, {"code": "PERMISSION_DENIED", "message": "no"}, "trace")
    assert isinstance(err, ForbiddenError)
    err = map_error(400, {"code": "VALIDATION_ERROR", "message": "bad"}, "trace")
    assert isinstance(err, ValidationError)


def test_error_mapper_common_failures() -> None:
    conflict = map_error(409, {"code": "CONFLICT", "message": "duplicate"}, "trace-409")
    assert conflict.status_code == 409
    assert conflict.trace_id == "trace-409"
    server = map_error(500, {"code": "SERVER_ERROR", "message": "oops"}, "trace-500")
    assert server.status_code == 500
    assert "trace_id=trace-500" in str(server)
