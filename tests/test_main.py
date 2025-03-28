import pytest
from fastapi.testclient import TestClient
from main import app
import os
from unittest.mock import patch, MagicMock
import asyncio
from fastapi import HTTPException
import httpx
import logging
from auth import create_access_token

# 配置测试日志
logger = logging.getLogger(__name__)

# 创建测试客户端
client = TestClient(app)

# 测试数据
TEST_USERNAME = "test_user"
TEST_PASSWORD = "test123"
TEST_RESPONSE = {"result": "test result"}

# 获取测试令牌
def get_test_token():
    """获取测试用的访问令牌"""
    return create_access_token({"sub": TEST_USERNAME})

# 模拟环境变量
@pytest.fixture(autouse=True)
def setup_env():
    """设置测试环境变量"""
    logger.info("Setting up test environment")
    os.environ["TESTING"] = "true"
    yield
    logger.info("Cleaning up test environment")
    if "TESTING" in os.environ:
        del os.environ["TESTING"]

# 基础功能测试
def test_health_check():
    """测试健康检查端点"""
    logger.info("Testing health check endpoint")
    response = client.get("/health")
    logger.debug(f"Health check response: {response.json()}")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

# 认证测试
def test_login_success():
    """测试登录成功"""
    logger.info("Testing successful login")
    response = client.post(
        "/token",
        data={
            "username": TEST_USERNAME,
            "password": TEST_PASSWORD
        }
    )
    logger.debug(f"Login response: {response.json()}")
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"

def test_login_failure():
    """测试登录失败"""
    logger.info("Testing failed login")
    response = client.post(
        "/token",
        data={
            "username": TEST_USERNAME,
            "password": "wrong_password"
        }
    )
    logger.debug(f"Login response: {response.json()}")
    assert response.status_code == 401
    assert response.json()["detail"] == "用户名或密码错误"

# API 访问测试
def test_scan_code_without_token():
    """测试不带令牌的扫描请求"""
    logger.info("Testing scan request without token")
    response = client.post(
        "/scan",
        json={
            "code": "def hello():\n    print('Hello')",
            "language": "python"
        }
    )
    logger.debug(f"Response status: {response.status_code}")
    assert response.status_code == 401

def test_scan_code_with_valid_token():
    """测试使用有效的令牌"""
    logger.info("Testing scan request with valid token")
    token = get_test_token()
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: TEST_RESPONSE,
            raise_for_status=lambda: None
        )
        
        response = client.post(
            "/scan",
            json={
                "code": "def hello():\n    print('Hello')",
                "language": "python"
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        logger.debug(f"Response: {response.json()}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "result" in data
        assert data["user_id"] == TEST_USERNAME

# 请求数据测试
def test_scan_with_empty_data():
    """测试空数据请求"""
    logger.info("Testing scan request with empty data")
    token = get_test_token()
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: TEST_RESPONSE,
            raise_for_status=lambda: None
        )
        
        response = client.post(
            "/scan",
            json={
                "code": "",
                "language": "python"
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        logger.debug(f"Response status: {response.status_code}")
        assert response.status_code == 200

def test_scan_with_large_data():
    """测试大数据请求"""
    logger.info("Testing scan request with large data")
    token = get_test_token()
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: TEST_RESPONSE,
            raise_for_status=lambda: None
        )
        
        response = client.post(
            "/scan",
            json={
                "code": "x" * 1000000,  # 1MB 数据
                "language": "python"
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        logger.debug(f"Response status: {response.status_code}")
        assert response.status_code == 200

# 错误处理测试
def test_scan_with_network_error():
    """测试网络错误"""
    logger.info("Testing scan request with network error")
    token = get_test_token()
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.side_effect = httpx.RequestError("Network error")
        
        response = client.post(
            "/scan",
            json={
                "code": "test code",
                "language": "python"
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        logger.debug(f"Response status: {response.status_code}")
        assert response.status_code == 500
        assert response.json()["detail"] == "AI service unavailable"

def test_scan_with_http_error():
    """测试 HTTP 错误"""
    logger.info("Testing scan request with HTTP error")
    token = get_test_token()
    with patch("httpx.AsyncClient.post") as mock_post:
        # 创建一个模拟的响应对象
        mock_response = MagicMock()
        mock_response.status_code = 500  # 设置具体的状态码
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "HTTP error", request=MagicMock(), response=mock_response
        )
        mock_post.return_value = mock_response
        
        response = client.post(
            "/scan",
            json={
                "code": "test code",
                "language": "python"
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        logger.debug(f"Response status: {response.status_code}")
        assert response.status_code == 500
        assert response.json()["detail"] == "AI service error"

# 超时测试
@pytest.mark.asyncio
async def test_scan_timeout():
    """测试请求超时"""
    logger.info("Testing scan request timeout")
    token = get_test_token()
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.side_effect = httpx.TimeoutException("Timeout")
        
        response = client.post(
            "/scan",
            json={
                "code": "test code",
                "language": "python"
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        logger.debug(f"Response status: {response.status_code}")
        assert response.status_code == 500
        assert response.json()["detail"] == "AI service unavailable"

# 并发测试
@pytest.mark.asyncio
async def test_concurrent_requests():
    """测试并发请求"""
    logger.info("Testing concurrent requests")
    token = get_test_token()
    async def make_request():
        return client.post(
            "/scan",
            json={
                "code": "test code",
                "language": "python"
            },
            headers={"Authorization": f"Bearer {token}"}
        )
    
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: TEST_RESPONSE,
            raise_for_status=lambda: None
        )
        
        # 创建 10 个并发请求
        tasks = [make_request() for _ in range(10)]
        responses = await asyncio.gather(*tasks)
        
        # 验证所有请求都成功
        for i, response in enumerate(responses):
            logger.debug(f"Response {i+1} status: {response.status_code}")
            assert response.status_code == 200
            assert response.json()["status"] == "success"

# 边界条件测试
def test_scan_with_special_characters():
    """测试特殊字符"""
    logger.info("Testing scan request with special characters")
    token = get_test_token()
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: TEST_RESPONSE,
            raise_for_status=lambda: None
        )
        
        response = client.post(
            "/scan",
            json={
                "code": "!@#$%^&*()_+{}[]|\\:;\"'<>,.?/~`",
                "language": "python"
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        logger.debug(f"Response status: {response.status_code}")
        assert response.status_code == 200

def test_scan_with_unicode_characters():
    """测试 Unicode 字符"""
    logger.info("Testing scan request with Unicode characters")
    token = get_test_token()
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: TEST_RESPONSE,
            raise_for_status=lambda: None
        )
        
        response = client.post(
            "/scan",
            json={
                "code": "你好，世界！",
                "language": "python"
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        logger.debug(f"Response status: {response.status_code}")
        assert response.status_code == 200 