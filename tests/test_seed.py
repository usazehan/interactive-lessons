"""Seed helper: happy-path data for exercising the section/block endpoints."""
import os
import unittest

os.environ.setdefault("DATABASE_PATH", ":memory:")

from fastapi.testclient import TestClient

from app.main import app
from app.seed import seed
from app.store import reset_db


class TestSeed(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        reset_db()

    def test_seed_creates_projects_ready_for_sections(self) -> None:
        projects = seed()
        self.assertGreaterEqual(len(projects), 1)

        # Projects are queryable through the API.
        listed = self.client.get("/projects").json()
        self.assertEqual(len(listed), len(projects))

        # And a section can be added to a seeded project.
        target = projects[-1]
        resp = self.client.post(
            f"/projects/{target.id}/sections", json={"title": "New section"}
        )
        self.assertEqual(resp.status_code, 201)

    def test_seeded_section_has_ordered_blocks_and_a_checkpoint(self) -> None:
        projects = seed()
        first = projects[0]

        sections = self.client.get(f"/projects/{first.id}/sections").json()
        self.assertEqual(len(sections), 1)
        sid = sections[0]["id"]

        blocks = self.client.get(
            f"/projects/{first.id}/sections/{sid}/blocks"
        ).json()
        # Blocks come back ordered by position.
        positions = [b["position"] for b in blocks]
        self.assertEqual(positions, sorted(positions))

        # The run covers the block types, including a checkpoint.
        types = {b["type"] for b in blocks}
        self.assertTrue({"text", "code_block", "image", "checkpoint"} <= types)
        # The text block is Markdown with an inline link.
        text_block = next(b for b in blocks if b["type"] == "text")
        self.assertIn("](https://", text_block["text_content"])
        checkpoint_block = next(b for b in blocks if b["type"] == "checkpoint")
        self.assertEqual(checkpoint_block["checkpoint"]["title"], "Confirm it runs")


if __name__ == "__main__":
    unittest.main()
