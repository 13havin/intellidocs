from fastapi.testclient import TestClient
from app.main import app

def test_user_creation_and_retrieval():

    client = TestClient(app)
    test_user_data = {"name": "test", "email": "test@ex.com"}
    response = client.post("/api/v1/users", json=test_user_data)
    
    assert response.status_code == 201
    assert response.json()["name"] == test_user_data["name"]
    assert response.json()["email"] == test_user_data["email"]
    
    user_id = response.json()["id"]
    get_response  = client.get(f"/api/v1/users/{user_id}")
    
    assert get_response.status_code == 200
    assert get_response.json()["name"] == test_user_data["name"]
    assert get_response.json()["email"] == test_user_data["email"]

    
def test_user_creation_same_email():

    client = TestClient(app)
    test_user_data = {"name": "test", "email": "test@ex.com"}
    response = client.post("/api/v1/users", json=test_user_data)
    
    assert response.status_code == 409
    
def test_get_nonexistent_user():
    
    client = TestClient(app)
    response = client.get("/api/v1/users/9999")
    
    assert response.status_code == 404

def test_user_creation_invalid_email():

    client = TestClient(app)
    test_user_data = {"name": "test", "email": "invalid-email"}
    response = client.post("/api/v1/users", json=test_user_data)
    
    assert response.status_code == 422