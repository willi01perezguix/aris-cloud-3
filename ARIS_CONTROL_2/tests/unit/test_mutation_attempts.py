from aris_control_2.app.application.mutation_attempts import begin_mutation, end_mutation, get_or_create_attempt
from aris_control_2.app.application.state.session_state import SessionState


def test_generates_new_idempotency_key_per_new_submit() -> None:
    state = SessionState()

    first = get_or_create_attempt(state, "store-create")
    state.pending_mutations.pop("store-create")
    second = get_or_create_attempt(state, "store-create")

    assert first.idempotency_key != second.idempotency_key
    assert first.transaction_id != second.transaction_id


def test_blocks_double_submit_while_mutation_is_loading() -> None:
    state = SessionState()

    first = begin_mutation(state, "user-create")
    second = begin_mutation(state, "user-create")
    end_mutation(state, "user-create")
    third = begin_mutation(state, "user-create")

    assert first is True
    assert second is False
    assert third is True
