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


def login(client, email="author@test.com", password="password123"):
    """Register + log in and set the bearer header on the client. Returns token."""
    token = token_for(client, email, password)
    client.headers.update(auth_header(token))
    return token
