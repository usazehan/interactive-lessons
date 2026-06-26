"""Registration, login, and token validation."""
import os
import unittest

os.environ.setdefault("DATABASE_PATH", ":memory:")

from fastapi.testclient import TestClient

from app.main import app
from app.store import reset_db


class TestAuth(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        reset_db()

    def _register(self, email="a@test.com", password="password123"):
        return self.client.post(
            "/auth/register", json={"email": email, "password": password}
        )

    def _login(self, email="a@test.com", password="password123"):
        return self.client.post(
            "/auth/login", data={"username": email, "password": password}
        )

    def test_register_login_me(self) -> None:
        reg = self._register()
        self.assertEqual(reg.status_code, 201)
        self.assertEqual(reg.json()["email"], "a@test.com")
        self.assertNotIn("password", reg.json())
        self.assertNotIn("hashed_password", reg.json())

        token = self._login().json()["access_token"]
        me = self.client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["email"], "a@test.com")

    def test_duplicate_email_rejected(self) -> None:
        self._register()
        self.assertEqual(self._register().status_code, 409)

    def test_short_password_rejected(self) -> None:
        self.assertEqual(self._register(password="short").status_code, 422)

    def test_wrong_password_rejected(self) -> None:
        self._register()
        self.assertEqual(self._login(password="nope").status_code, 401)

    def test_me_requires_valid_token(self) -> None:
        self.assertEqual(self.client.get("/auth/me").status_code, 401)
        self.assertEqual(
            self.client.get(
                "/auth/me", headers={"Authorization": "Bearer not-a-jwt"}
            ).status_code,
            401,
        )


if __name__ == "__main__":
    unittest.main()
