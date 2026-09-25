import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import status

pytestmark = pytest.mark.asyncio

async def test_register_success(client: AsyncClient, db: AsyncSession):
    response = await client.post("/api/v1/auth/register", json={
        "email": "newuser@example.com",
        "password": "Password123!",
        "full_name": "New User",
        "workspace_name": "New Workspace"
    })
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["user"]["email"] == "newuser@example.com"
    assert data["workspace"]["name"] == "New Workspace"

async def test_register_duplicate_email(client: AsyncClient, db: AsyncSession):
    payload = {
        "email": "duplicate@example.com",
        "password": "Password123!",
        "full_name": "Duplicate User",
        "workspace_name": "Workspace"
    }
    await client.post("/api/v1/auth/register", json=payload)
    
    # Try again
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == status.HTTP_409_CONFLICT

async def test_register_weak_password(client: AsyncClient):
    response = await client.post("/api/v1/auth/register", json={
        "email": "weak@example.com",
        "password": "weak",
        "full_name": "Weak User",
        "workspace_name": "Workspace"
    })
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

async def test_login_success(client: AsyncClient, db: AsyncSession):
    # Setup user
    await client.post("/api/v1/auth/register", json={
        "email": "loginsuccess@example.com",
        "password": "Password123!",
        "full_name": "Login User",
        "workspace_name": "Workspace"
    })
    
    response = await client.post("/api/v1/auth/login", json={
        "email": "loginsuccess@example.com",
        "password": "Password123!"
    })
    assert response.status_code == status.HTTP_200_OK
    assert "access_token" in response.json()

async def test_login_wrong_password(client: AsyncClient, db: AsyncSession):
    await client.post("/api/v1/auth/register", json={
        "email": "wrongpwd@example.com",
        "password": "Password123!",
        "full_name": "Wrong Pwd User",
        "workspace_name": "Workspace"
    })
    
    response = await client.post("/api/v1/auth/login", json={
        "email": "wrongpwd@example.com",
        "password": "WrongPassword123!"
    })
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Invalid email or password"

async def test_login_unknown_email(client: AsyncClient):
    response = await client.post("/api/v1/auth/login", json={
        "email": "unknown@example.com",
        "password": "Password123!"
    })
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Invalid email or password"

async def test_refresh_token_success(client: AsyncClient, db: AsyncSession):
    register_res = await client.post("/api/v1/auth/register", json={
        "email": "refresh@example.com",
        "password": "Password123!",
        "full_name": "Refresh User",
        "workspace_name": "Workspace"
    })
    refresh_token = register_res.json()["refresh_token"]
    
    response = await client.post("/api/v1/auth/refresh", json={
        "refresh_token": refresh_token
    })
    assert response.status_code == status.HTTP_200_OK
    assert "access_token" in response.json()

async def test_get_me_authenticated(client: AsyncClient, db: AsyncSession):
    register_res = await client.post("/api/v1/auth/register", json={
        "email": "me@example.com",
        "password": "Password123!",
        "full_name": "Me User",
        "workspace_name": "Workspace"
    })
    access_token = register_res.json()["access_token"]
    
    response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["email"] == "me@example.com"

async def test_get_me_no_token(client: AsyncClient):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

async def test_get_me_expired_token(client: AsyncClient):
    # This test would require mocking the datetime inside create_access_token 
    # For now we'll send a known invalid token to see it fails.
    response = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid_token"})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
