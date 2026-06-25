"""Project -> section -> content block -> checkpoint -> input flow.

Forces an in-memory DB before importing the app (set here as well as in the
sibling test modules, since whichever is imported first must win) and resets
all tables between cases so they stay independent.
"""
import os
import unittest

os.environ.setdefault("DATABASE_PATH", ":memory:")

from fastapi.testclient import TestClient

from app.main import app
from app.store import reset_db


class TestSectionsFlow(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        reset_db()
        self.project = self.client.post("/projects", json={"name": "P"}).json()
        self.section = self.client.post(
            f"/projects/{self.project['id']}/sections", json={"title": "Intro"}
        ).json()

    def _blocks_url(self) -> str:
        return f"/projects/{self.project['id']}/sections/{self.section['id']}/blocks"

    def _section_url(self) -> str:
        return f"/projects/{self.project['id']}/sections/{self.section['id']}"

    # --- sections ---

    def test_sections_auto_position_and_order(self) -> None:
        pid = self.project["id"]
        # setUp already made one section at position 0; add two more.
        s1 = self.client.post(f"/projects/{pid}/sections", json={"title": "B"}).json()
        s2 = self.client.post(f"/projects/{pid}/sections", json={"title": "C"}).json()
        self.assertEqual([self.section["position"], s1["position"], s2["position"]], [0, 1, 2])

        listed = self.client.get(f"/projects/{pid}/sections").json()
        self.assertEqual([s["title"] for s in listed], ["Intro", "B", "C"])

    def test_section_scoped_to_project(self) -> None:
        other = self.client.post("/projects", json={"name": "Other"}).json()
        resp = self.client.get(
            f"/projects/{other['id']}/sections/{self.section['id']}"
        )
        self.assertEqual(resp.status_code, 404)

    def test_missing_project_returns_404(self) -> None:
        self.assertEqual(self.client.get("/projects/999/sections").status_code, 404)

    # --- content blocks ---

    def test_all_block_types_and_ordering(self) -> None:
        url = self._blocks_url()
        payloads = [
            {"type": "text", "text_content": "See the [docs](https://ex.com) and `make`."},
            {"type": "code_block", "code_content": "print(1)", "keyword_metadata": "python"},
            {"type": "image", "image_url": "https://ex.com/a.png"},
            {"type": "checkpoint", "title": "Try it"},
        ]
        for body in payloads:
            self.assertEqual(self.client.post(url, json=body).status_code, 201)

        blocks = self.client.get(url).json()
        self.assertEqual(
            [(b["position"], b["type"]) for b in blocks],
            [(0, "text"), (1, "code_block"), (2, "image"), (3, "checkpoint")],
        )

    def test_link_is_not_a_block_type(self) -> None:
        # Links live inside text_content (Markdown), not as their own block.
        resp = self.client.post(
            self._blocks_url(), json={"type": "link", "text_content": "x"}
        )
        self.assertEqual(resp.status_code, 422)

    def test_block_rejects_invalid_url(self) -> None:
        resp = self.client.post(
            self._blocks_url(), json={"type": "image", "image_url": "not a url"}
        )
        self.assertEqual(resp.status_code, 422)

    def test_block_rejects_mismatched_fields(self) -> None:
        url = self._blocks_url()
        # text block carrying an image_url
        self.assertEqual(
            self.client.post(
                url, json={"type": "text", "text_content": "x", "image_url": "https://e.com/a.png"}
            ).status_code,
            422,
        )
        # missing the required field for the type
        self.assertEqual(
            self.client.post(url, json={"type": "text"}).status_code, 422
        )
        # title on a non-checkpoint block
        self.assertEqual(
            self.client.post(
                url, json={"type": "text", "text_content": "x", "title": "nope"}
            ).status_code,
            422,
        )
        # checkpoint block without a title
        self.assertEqual(
            self.client.post(url, json={"type": "checkpoint"}).status_code, 422
        )

    def test_block_under_missing_section_404(self) -> None:
        resp = self.client.post(
            f"/projects/{self.project['id']}/sections/999/blocks",
            json={"type": "text", "text_content": "x"},
        )
        self.assertEqual(resp.status_code, 404)

    # --- checkpoints ---

    def test_checkpoint_block_creates_checkpoint(self) -> None:
        block = self.client.post(
            self._blocks_url(), json={"type": "checkpoint", "title": "Confirm"}
        ).json()
        self.assertIsNotNone(block["checkpoint_id"])
        self.assertEqual(block["checkpoint"]["title"], "Confirm")

        checkpoints = self.client.get(f"{self._section_url()}/checkpoints").json()
        self.assertEqual(len(checkpoints), 1)

    # --- cascades + integrity ---

    def test_deleting_section_cascades(self) -> None:
        self.client.post(
            self._blocks_url(), json={"type": "checkpoint", "title": "C"}
        )
        self.assertEqual(self.client.delete(self._section_url()).status_code, 204)
        self.assertEqual(self.client.get(self._section_url()).status_code, 404)

    def test_deleting_checkpoint_block_removes_checkpoint(self) -> None:
        block = self.client.post(
            self._blocks_url(), json={"type": "checkpoint", "title": "C"}
        ).json()
        self.client.delete(f"{self._blocks_url()}/{block['id']}")
        self.assertEqual(
            self.client.get(f"{self._section_url()}/checkpoints").json(), []
        )

    def test_foreign_keys_enforced_at_db_level(self) -> None:
        from sqlalchemy.exc import IntegrityError

        from app.db import SessionLocal, SessionResponseORM

        # A response pointing at a non-existent reading session is rejected.
        with self.assertRaises(IntegrityError):
            with SessionLocal() as s:
                s.add(SessionResponseORM(session_id=99999, checkpoint_id=1, text="x"))
                s.commit()


if __name__ == "__main__":
    unittest.main()
