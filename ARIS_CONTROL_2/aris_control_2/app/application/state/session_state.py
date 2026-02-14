from dataclasses import dataclass, field

from aris_control_2.app.domain.models.session_context import SessionContext


@dataclass
class SessionState:
    context: SessionContext = field(default_factory=SessionContext)
