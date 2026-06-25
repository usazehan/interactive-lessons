"""Reading sessions: snapshot isolation, optimistic locking, and responses.

User A reads a pinned snapshot while User B autosaves edits to the same
project; A must be unaffected until they opt in via /refresh.
"""
import os
import unittest

os.environ.setdefault("DATABASE_PATH", ":memory:")

from fastapi.testclient import TestClient

from app.main import app
from app.store import reset_db


class TestReadingSessions(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        reset_db()
        # User B authors a project with one section and a couple of blocks.
        self.pid = self.client.post("/projects", json={"name": "P"}).json()["id"]
        self.sid = self.client.post(
            f"/projects/{self.pid}/sections", json={"title": "Intro"}
        ).json()["id"]
        self._blocks = f"/projects/{self.pid}/sections/{self.sid}/blocks"
        self.client.post(self._blocks, json={"type": "text", "text_content": "Step one"})
        self.checkpoint_id = self.client.post(
            self._blocks, json={"type": "checkpoint", "title": "Do it"}
        ).json()["checkpoint_id"]

    def _start_session(self, user: str = "userA") -> dict:
        return self.client.post(
            f"/projects/{self.pid}/sessions", json={"user_id": user}
        ).json()

    def test_snapshot_isolated_from_author_edits(self) -> None:
        session = self._start_session()
        sess_id = session["id"]
        before = [b["type"] for b in session["snapshot"]["sections"][0]["blocks"]]

        # B edits after A snapshotted: add a block, delete the text block.
        self.client.post(
            self._blocks, json={"type": "text", "text_content": "NEW from B"}
        )

        # A re-reads the session -> identical to the pinned snapshot.
        a_view = self.client.get(f"/projects/{self.pid}/sessions/{sess_id}").json()
        after = [b["type"] for b in a_view["snapshot"]["sections"][0]["blocks"]]
        self.assertEqual(before, after)
        texts = [
            b.get("text_content")
            for b in a_view["snapshot"]["sections"][0]["blocks"]
            if b["type"] == "text"
        ]
        self.assertNotIn("NEW from B", texts)

    def test_refresh_picks_up_latest(self) -> None:
        session = self._start_session()
        sess_id = session["id"]
        pinned_version = session["project_version"]

        self.client.post(
            self._blocks, json={"type": "text", "text_content": "added later"}
        )
        refreshed = self.client.post(
            f"/projects/{self.pid}/sessions/{sess_id}/refresh"
        ).json()
        self.assertGreater(refreshed["project_version"], pinned_version)
        self.assertFalse(refreshed["is_stale"])
        self.assertGreater(
            len(refreshed["snapshot"]["sections"][0]["blocks"]),
            len(session["snapshot"]["sections"][0]["blocks"]),
        )

    def test_staleness_is_surfaced(self) -> None:
        session = self._start_session()
        sess_id = session["id"]
        self.assertFalse(session["is_stale"])
        self.assertEqual(session["latest_version"], session["project_version"])

        # B edits -> A's existing snapshot is now behind.
        self.client.post(
            self._blocks, json={"type": "text", "text_content": "newer"}
        )
        a_view = self.client.get(f"/projects/{self.pid}/sessions/{sess_id}").json()
        self.assertTrue(a_view["is_stale"])
        self.assertGreater(a_view["latest_version"], a_view["project_version"])

    def test_start_is_get_or_resume(self) -> None:
        first = self._start_session("userA")
        # B edits in between; re-starting resumes the SAME (pinned) session.
        self.client.post(
            self._blocks, json={"type": "text", "text_content": "newer"}
        )
        second = self._start_session("userA")
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(first["project_version"], second["project_version"])
        self.assertTrue(second["is_stale"])

    def test_prune_removes_idle_sessions(self) -> None:
        from datetime import datetime, timedelta

        from app.db import ReadingSessionORM, SessionLocal
        from app.store import prune_stale_sessions

        session = self._start_session()
        # Age the session past the TTL.
        with SessionLocal() as s:
            row = s.get(ReadingSessionORM, session["id"])
            row.last_accessed_at = datetime.utcnow() - timedelta(days=400)
            s.commit()

        self.assertEqual(prune_stale_sessions(), 1)
        self.assertEqual(
            self.client.get(f"/projects/{self.pid}/sessions/{session['id']}").status_code,
            404,
        )

    def test_cleanup_cli_prunes(self) -> None:
        from datetime import datetime, timedelta

        from app.cleanup import main
        from app.db import ReadingSessionORM, SessionLocal

        session = self._start_session()
        with SessionLocal() as s:
            row = s.get(ReadingSessionORM, session["id"])
            row.last_accessed_at = datetime.utcnow() - timedelta(days=400)
            s.commit()

        # The CLI returns how many it pruned.
        self.assertEqual(main([]), 1)
        self.assertEqual(main([]), 0)

    def test_optimistic_lock_rejects_stale_edit(self) -> None:
        version = self.client.get(f"/projects/{self.pid}").json()["version"]

        # Stale If-Match -> 409.
        stale = self.client.post(
            self._blocks,
            headers={"If-Match": "1"},
            json={"type": "text", "text_content": "stale"},
        )
        self.assertEqual(stale.status_code, 409)

        # Current version -> 201, and the ETag advances.
        fresh = self.client.post(
            self._blocks,
            headers={"If-Match": str(version)},
            json={"type": "text", "text_content": "fresh"},
        )
        self.assertEqual(fresh.status_code, 201)
        self.assertEqual(fresh.headers["etag"], str(version + 1))

    def test_no_if_match_is_last_write_wins(self) -> None:
        # Omitting If-Match is allowed (autosave without a precondition).
        resp = self.client.post(
            self._blocks, json={"type": "text", "text_content": "ok"}
        )
        self.assertEqual(resp.status_code, 201)

    def test_responses_are_per_session(self) -> None:
        a = self._start_session("userA")
        b = self._start_session("userB")
        url_a = f"/projects/{self.pid}/sessions/{a['id']}/checkpoints/{self.checkpoint_id}/responses"
        url_b = f"/projects/{self.pid}/sessions/{b['id']}/checkpoints/{self.checkpoint_id}/responses"

        self.assertEqual(self.client.post(url_a, json={"text": "A's answer"}).status_code, 201)
        self.assertEqual(
            self.client.post(url_b, json={"link": "https://b.example.com"}).status_code, 201
        )
        # at least one of text/link required
        self.assertEqual(self.client.post(url_a, json={}).status_code, 422)

        # Each reader sees only their own responses.
        a_responses = self.client.get(url_a).json()
        b_responses = self.client.get(url_b).json()
        self.assertEqual([r["text"] for r in a_responses], ["A's answer"])
        self.assertEqual(len(b_responses), 1)
        self.assertIsNone(b_responses[0]["text"])

    def test_response_for_unknown_checkpoint_404(self) -> None:
        session = self._start_session()
        url = f"/projects/{self.pid}/sessions/{session['id']}/checkpoints/99999/responses"
        self.assertEqual(self.client.post(url, json={"text": "x"}).status_code, 404)

    def test_session_scoped_to_project(self) -> None:
        session = self._start_session()
        other = self.client.post("/projects", json={"name": "Other"}).json()["id"]
        resp = self.client.get(f"/projects/{other}/sessions/{session['id']}")
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
