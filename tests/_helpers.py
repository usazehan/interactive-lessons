"""Shared test helpers for authentication."""


def token_for(client, email, password="password123"):
    """Register (idempotently) and log in; return a bearer access token."""
    client.post("/auth/register", json={"email": email, "password": password})
    resp = client.post(
        "/auth/login", data={"username": email, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def verify(email):
    """Mark a registered user verified (so they can author). Test-only shortcut."""
    from app.store import user_store

    user = user_store.get_orm_by_email(email)
    if user is not None and user.verification_token is not None:
        user_store.verify_by_token(user.verification_token)


def login(client, email="author@test.com", password="password123"):
    """Register, verify, log in, and set the bearer header. Returns the token."""
    client.post("/auth/register", json={"email": email, "password": password})
    verify(email)
    token = token_for(client, email, password)
    client.headers.update(auth_header(token))
    return token
