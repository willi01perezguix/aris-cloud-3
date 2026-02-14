from __future__ import annotations

from dataclasses import dataclass

from aris_control_2.app.application.state.session_state import SessionState
from aris_control_2.app.infrastructure.idempotency.key_factory import IdempotencyKeyFactory
from aris_control_2.clients.aris3_client_sdk.tracing import new_trace_id


@dataclass(frozen=True)
class MutationAttempt:
    idempotency_key: str
    transaction_id: str


def get_or_create_attempt(state: SessionState, operation: str) -> MutationAttempt:
    cached = state.pending_mutations.get(operation)
    if cached:
        return MutationAttempt(
            idempotency_key=cached["idempotency_key"],
            transaction_id=cached["transaction_id"],
        )

    attempt = MutationAttempt(
        idempotency_key=IdempotencyKeyFactory.new_key(operation),
        transaction_id=new_trace_id(),
    )
    state.pending_mutations[operation] = {
        "idempotency_key": attempt.idempotency_key,
        "transaction_id": attempt.transaction_id,
    }
    return attempt


def clear_attempt(state: SessionState, operation: str) -> None:
    state.pending_mutations.pop(operation, None)


def begin_mutation(state: SessionState, operation: str) -> bool:
    if operation in state.mutation_in_flight:
        return False
    state.mutation_in_flight.add(operation)
    return True


def end_mutation(state: SessionState, operation: str) -> None:
    state.mutation_in_flight.discard(operation)
