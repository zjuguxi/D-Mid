import pytest
from fastapi.testclient import TestClient
from main import app
import os
from unittest.mock import patch, MagicMock
import asyncio
from fastapi import HTTPException
import httpx
import logging

# 配置测试日志
logger = logging.getLogger(__name__)

# 创建测试客户端
client = TestClient(app)

# 测试数据
TEST_API_KEY = "test-api-key"
TEST_USER_ID = "test_user"
TEST_RESPONSE = {"result": "test result"}

# 模拟环境变量
@pytest.fixture(autouse=True)
def setup_env():
    """设置测试环境变量"""
    logger.info("Setting up test environment")
    os.environ["TESTING"] = "true"
    os.environ["API_KEY_TEST_USER"] = TEST_API_KEY
    yield
    logger.info("Cleaning up test environment")
    if "API_KEY_TEST_USER" in os.environ:
        del os.environ["API_KEY_TEST_USER"]
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

# API Key 验证测试
def test_scan_without_api_key():
    """测试不带 API key 的扫描请求"""
    logger.info("Testing scan request without API key")
    response = client.post("/scan", json={"code": "test code"})
    logger.debug(f"Response status: {response.status_code}")
    assert response.status_code == 401
    assert response.json()["detail"] == "API key required"

def test_scan_with_invalid_api_key():
    """测试使用无效的 API key"""
    logger.info("Testing scan request with invalid API key")
    response = client.post(
        "/scan",
        json={"code": "test code"},
        headers={"X-API-Key": "invalid-key"}
    )
    logger.debug(f"Response status: {response.status_code}")
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid API key"

def test_scan_with_valid_api_key():
    """测试使用有效的 API key"""
    logger.info("Testing scan request with valid API key")
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: TEST_RESPONSE,
            raise_for_status=lambda: None
        )
        
        response = client.post(
            "/scan",
            json={"code": "test code"},
            headers={"X-API-Key": TEST_API_KEY}
        )
        logger.debug(f"Response: {response.json()}")
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        assert response.json()["result"] == TEST_RESPONSE
        assert response.json()["user_id"] == TEST_USER_ID

# 请求数据测试
def test_scan_with_empty_data():
    """测试空数据请求"""
    logger.info("Testing scan request with empty data")
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: TEST_RESPONSE,
            raise_for_status=lambda: None
        )
        
        response = client.post(
            "/scan",
            json={},
            headers={"X-API-Key": TEST_API_KEY}
        )
        logger.debug(f"Response status: {response.status_code}")
        assert response.status_code == 200

def test_scan_with_large_data():
    """测试大数据请求"""
    logger.info("Testing scan request with large data")
    large_data = {"code": "x" * 1000000}  # 1MB 数据
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: TEST_RESPONSE,
            raise_for_status=lambda: None
        )
        
        response = client.post(
            "/scan",
            json=large_data,
            headers={"X-API-Key": TEST_API_KEY}
        )
        logger.debug(f"Response status: {response.status_code}")
        assert response.status_code == 200

# 错误处理测试
def test_scan_with_network_error():
    """测试网络错误"""
    logger.info("Testing scan request with network error")
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.side_effect = httpx.RequestError("Network error")
        
        response = client.post(
            "/scan",
            json={"code": "test code"},
            headers={"X-API-Key": TEST_API_KEY}
        )
        logger.debug(f"Response status: {response.status_code}")
        assert response.status_code == 500
        assert response.json()["detail"] == "AI service unavailable"

def test_scan_with_http_error():
    """测试 HTTP 错误"""
    logger.info("Testing scan request with HTTP error")
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
            json={"code": "test code"},
            headers={"X-API-Key": TEST_API_KEY}
        )
        logger.debug(f"Response status: {response.status_code}")
        assert response.status_code == 500
        assert response.json()["detail"] == "AI service error"

# 超时测试
@pytest.mark.asyncio
async def test_scan_timeout():
    """测试请求超时"""
    logger.info("Testing scan request timeout")
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.side_effect = httpx.TimeoutException("Timeout")
        
        response = client.post(
            "/scan",
            json={"code": "test code"},
            headers={"X-API-Key": TEST_API_KEY}
        )
        logger.debug(f"Response status: {response.status_code}")
        assert response.status_code == 500
        assert response.json()["detail"] == "AI service unavailable"

# 并发测试
@pytest.mark.asyncio
async def test_concurrent_requests():
    """测试并发请求"""
    logger.info("Testing concurrent requests")
    async def make_request():
        return client.post(
            "/scan",
            json={"code": "test code"},
            headers={"X-API-Key": TEST_API_KEY}
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
    special_data = {"code": "!@#$%^&*()_+{}[]|\\:;\"'<>,.?/~`"}
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: TEST_RESPONSE,
            raise_for_status=lambda: None
        )
        
        response = client.post(
            "/scan",
            json=special_data,
            headers={"X-API-Key": TEST_API_KEY}
        )
        logger.debug(f"Response status: {response.status_code}")
        assert response.status_code == 200

def test_scan_with_unicode_characters():
    """测试 Unicode 字符"""
    logger.info("Testing scan request with Unicode characters")
    unicode_data = {"code": "你好，世界！"}
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: TEST_RESPONSE,
            raise_for_status=lambda: None
        )
        
        response = client.post(
            "/scan",
            json=unicode_data,
            headers={"X-API-Key": TEST_API_KEY}
        )
        logger.debug(f"Response status: {response.status_code}")
        assert response.status_code == 200 