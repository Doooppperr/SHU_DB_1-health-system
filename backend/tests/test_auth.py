def test_me_requires_auth(client):
    response = client.get("/api/users/me")
    assert response.status_code == 401


def test_register_login_and_get_me(client):
    register_payload = {
        "username": "alice",
        "password": "secret123",
        "email": "alice@example.com",
    }
    register_response = client.post("/api/auth/register", json=register_payload)
    assert register_response.status_code == 201

    login_response = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "secret123"},
    )
    assert login_response.status_code == 200
    tokens = login_response.get_json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens

    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    me_response = client.get("/api/users/me", headers=headers)
    assert me_response.status_code == 200
    data = me_response.get_json()
    assert data["user"]["username"] == "alice"


def test_login_with_invalid_password_returns_401(client):
    client.post(
        "/api/auth/register",
        json={"username": "bob", "password": "secret123", "email": "bob@example.com"},
    )

    response = client.post(
        "/api/auth/login",
        json={"username": "bob", "password": "wrong-password"},
    )
    assert response.status_code == 401


def test_refresh_token_flow(client):
    client.post(
        "/api/auth/register",
        json={"username": "carol", "password": "secret123", "email": "carol@example.com"},
    )

    login_response = client.post(
        "/api/auth/login",
        json={"username": "carol", "password": "secret123"},
    )
    refresh_token = login_response.get_json()["refresh_token"]

    refresh_response = client.post(
        "/api/auth/refresh",
        headers={"Authorization": f"Bearer {refresh_token}"},
    )

    assert refresh_response.status_code == 200
    assert "access_token" in refresh_response.get_json()
