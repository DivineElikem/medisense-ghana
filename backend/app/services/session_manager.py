from uuid import UUID, uuid4
from typing import Dict, Optional
from app.models.session import SessionState, Stage

class SessionManager:
    def __init__(self):
        # In-memory storage for MVP. For production, use Redis or a DB.
        self.sessions: Dict[UUID, SessionState] = {}

    def create_session(self) -> SessionState:
        session = SessionState(session_id=uuid4())
        self.sessions[session.session_id] = session
        return session

    def get_session(self, session_id: UUID) -> Optional[SessionState]:
        return self.sessions.get(session_id)

    def update_session(self, session: SessionState):
        self.sessions[session.session_id] = session

# Singleton instance
session_manager = SessionManager()
