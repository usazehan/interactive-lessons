"""Health endpoint tests."""
import os
import unittest

os.environ.setdefault("DATABASE_PATH", ":memory:")

from fastapi.testclient import TestClient

from app.main import app


class TestHealth(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_health_ok(self) -> None:
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "ok")

    def test_root(self) -> None:
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("docs", resp.json())


if __name__ == "__main__":
    unittest.main()
