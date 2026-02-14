from aris_control_2.app.ui.components.mutation_feedback import print_mutation_error
from aris_control_2.clients.aris3_client_sdk.http_client import APIError


def test_print_mutation_error_uses_standard_fields(capsys) -> None:
    err = APIError(code="HTTP_500", message="boom", trace_id="trace-500")

    print_mutation_error("user.set_status", err)

    out = capsys.readouterr().out.strip()
    assert "operation=user.set_status" in out
    assert "code=HTTP_500" in out
    assert "message=boom" in out
    assert "trace_id=trace-500" in out
