"""Registration, login, and token validation."""
import os
import unittest

os.environ.setdefault("DATABASE_PATH", ":memory:")

from fastapi.testclient import TestClient

from _helpers import verify
from app.main import app
from app.store import reset_db, user_store


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

    def _registered_login(self, email="a@test.com", password="password123"):
        """Register, verify, and log in; return the token pair JSON."""
        self._register(email, password)
        verify(email)
        return self._login(email, password).json()

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

    # --- refresh / logout ---

    def test_login_returns_token_pair(self) -> None:
        tokens = self._registered_login()
        self.assertIn("access_token", tokens)
        self.assertIn("refresh_token", tokens)

    def test_refresh_rotates_and_invalidates_old(self) -> None:
        tokens = self._registered_login()
        refreshed = self.client.post(
            "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )
        self.assertEqual(refreshed.status_code, 200)
        self.assertNotEqual(
            refreshed.json()["refresh_token"], tokens["refresh_token"]
        )
        # The old refresh token is now consumed (rotation).
        reused = self.client.post(
            "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )
        self.assertEqual(reused.status_code, 401)

    def test_logout_revokes_refresh(self) -> None:
        tokens = self._registered_login()
        self.assertEqual(
            self.client.post(
                "/auth/logout", json={"refresh_token": tokens["refresh_token"]}
            ).status_code,
            204,
        )
        self.assertEqual(
            self.client.post(
                "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
            ).status_code,
            401,
        )

    # --- email verification ---

    def test_verify_email_flow(self) -> None:
        self._register()
        user = user_store.get_orm_by_email("a@test.com")
        self.assertFalse(user.is_verified)
        resp = self.client.post(
            "/auth/verify-email", json={"token": user.verification_token}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["is_verified"])
        # A bad token is rejected.
        self.assertEqual(
            self.client.post(
                "/auth/verify-email", json={"token": "nope"}
            ).status_code,
            400,
        )

    def test_unverified_cannot_author_until_verified(self) -> None:
        self._register()
        token = self._login().json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        self.assertEqual(
            self.client.post(
                "/projects", json={"name": "P"}, headers=headers
            ).status_code,
            403,
        )
        verify("a@test.com")
        self.assertEqual(
            self.client.post(
                "/projects", json={"name": "P"}, headers=headers
            ).status_code,
            201,
        )

    # --- password reset ---

    def test_password_reset_flow(self) -> None:
        tokens = self._registered_login()
        # Forgot-password doesn't leak whether the email exists.
        self.assertEqual(
            self.client.post(
                "/auth/forgot-password", json={"email": "a@test.com"}
            ).status_code,
            202,
        )
        reset_token = user_store.get_orm_by_email("a@test.com").reset_token
        self.assertEqual(
            self.client.post(
                "/auth/reset-password",
                json={"token": reset_token, "new_password": "newpassword123"},
            ).status_code,
            204,
        )
        # Old password no longer works; new one does.
        self.assertEqual(self._login(password="password123").status_code, 401)
        self.assertEqual(self._login(password="newpassword123").status_code, 200)
        # The reset revoked existing refresh tokens.
        self.assertEqual(
            self.client.post(
                "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
            ).status_code,
            401,
        )

    # --- roles ---

    def test_admin_bypasses_ownership(self) -> None:
        from _helpers import auth_header, token_for

        owner = TestClient(app)
        from _helpers import login

        login(owner, "owner@test.com")
        pid = owner.post("/projects", json={"name": "P"}).json()["id"]

        admin = TestClient(app)
        admin_token = token_for(admin, "admin@test.com")
        user_store.set_role(user_store.get_orm_by_email("admin@test.com").id, "admin")
        admin.headers.update(auth_header(admin_token))
        # Admin edits a project they don't own.
        self.assertEqual(
            admin.post(f"/projects/{pid}/sections", json={"title": "S"}).status_code,
            201,
        )


if __name__ == "__main__":
    unittest.main()
