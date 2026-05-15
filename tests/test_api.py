"""API 测试脚本"""
import requests
import json
import sys

BASE_URL = "http://localhost:5000"
HEADERS = {}

def test(name, method, url, **kwargs):
    try:
        if method == "GET":
            r = requests.get(url, **kwargs)
        elif method == "POST":
            r = requests.post(url, **kwargs)
        elif method == "PUT":
            r = requests.put(url, **kwargs)
        elif method == "DELETE":
            r = requests.delete(url, **kwargs)
        print(f"✅ {name}: {r.status_code} {r.text[:100]}")
    except Exception as e:
        print(f"❌ {name}: {e}")

def main():
    print("=" * 50)
    print("快回复后端 API 测试")
    print("=" * 50)
    print()

    # 健康检查
    test("健康检查", "GET", f"{BASE_URL}/health")

    # 注册
    test("用户注册", "POST", f"{BASE_URL}/api/auth/register",
         json={"username": "testuser", "password": "123456", "email": "test@test.com"})
    
    # 注册重复用户名
    test("重复注册", "POST", f"{BASE_URL}/api/auth/register",
         json={"username": "testuser", "password": "123456"})

    # 登录
    resp = requests.post(f"{BASE_URL}/api/auth/login",
                        json={"username": "testuser", "password": "123456"})
    data = resp.json()
    if data.get("data"):
        token = data["data"]["token"]
        HEADERS["Authorization"] = token
        print(f"✅ 登录成功，Token: {token[:20]}...")

    if HEADERS.get("Authorization"):
        # 获取资料
        test("获取资料", "GET", f"{BASE_URL}/api/auth/profile", headers=HEADERS)
        # 备份列表
        test("备份列表", "GET", f"{BASE_URL}/api/backup/list", headers=HEADERS)
        # 备份统计
        test("备份统计", "GET", f"{BASE_URL}/api/backup/stats", headers=HEADERS)

if __name__ == "__main__":
    main()