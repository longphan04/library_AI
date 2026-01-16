"""
Minimal fake in-memory database used only for local testing.
Provides hooks used by the API: chat session storage (in-memory) and simple job list.
"""
from typing import Dict, Any, List
import time

class FakeDatabase:
    def __init__(self):
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._jobs: Dict[str, Dict[str, Any]] = {}

    # Chat session helpers
    def load_session(self, session_id: str) -> Dict[str, Any]:
        return self._sessions.get(session_id, {"id": session_id, "created_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), "messages": []})

    def save_session(self, session: Dict[str, Any]):
        self._sessions[session["id"]] = session

    def delete_session(self, session_id: str):
        if session_id in self._sessions:
            del self._sessions[session_id]

    # Jobs
    def create_job(self, job: Dict[str, Any]):
        self._jobs[job["id"]] = job

    def list_jobs(self) -> List[Dict[str, Any]]:
        return list(self._jobs.values())

    def get_job(self, job_id: str) -> Dict[str, Any]:
        return self._jobs.get(job_id)

# Export a factory

def create_fake_database():
    return FakeDatabase()

