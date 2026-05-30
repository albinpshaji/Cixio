import requests

# 1. Register/Login
base_url = "http://127.0.0.1:8001"
user_data = {"email": "test@test.com", "password": "password", "full_name": "Test"}
requests.post(f"{base_url}/api/v1/auth/register", json=user_data)
resp = requests.post(f"{base_url}/api/v1/auth/login", json={"email": "test@test.com", "password": "password"})
token = resp.json()["access_token"]
print("Got token")

# 2. Upload
headers = {"Authorization": f"Bearer {token}"}
files = {"file": open("requirements.txt", "rb")}
resp = requests.post(f"{base_url}/api/v1/documents/upload", headers=headers, files=files)
print(resp.status_code)
print(resp.text)
