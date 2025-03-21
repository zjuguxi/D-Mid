from fastapi import FastAPI, HTTPException, Depends, Header
import httpx
import logging
import os
from typing import Optional, Dict

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

app = FastAPI(title="D-Mid Middleware")

# 模拟公共 AI API 地址
PUBLIC_AI_API_URL = os.getenv("PUBLIC_AI_API_URL", "https://api.example.com/scan")

# 用户 API 密钥（模拟数据库，实际可用 Redis 或数据库）
def get_valid_api_keys() -> Dict[str, str]:
    """获取有效的 API 密钥，支持测试环境"""
    if os.getenv("TESTING"):
        return {
            "test_user": os.getenv("API_KEY_TEST_USER", "test-api-key")
        }
    return {
        "user1": os.getenv("API_KEY_USER1", "secret-key-123"),
        "user2": os.getenv("API_KEY_USER2", "secret-key-456")
    }

# 认证依赖函数
async def verify_api_key(x_api_key: Optional[str] = Header(None)):
    if not x_api_key:
        logger.warning("Missing API key")
        raise HTTPException(status_code=401, detail="API key required")
    
    # 检查密钥是否有效并返回用户ID
    valid_keys = get_valid_api_keys()
    for user_id, key in valid_keys.items():
        if x_api_key == key:
            return user_id
    logger.warning(f"Invalid API key: {x_api_key}")
    raise HTTPException(status_code=401, detail="Invalid API key")

# 健康检查端点
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# 代码扫描端点
@app.post("/scan")
async def scan_code(
    request_data: dict,
    user_id: str = Depends(verify_api_key)
):
    # 优化日志显示，避免显示大量数据
    log_data = request_data.copy()
    if "code" in log_data and len(str(log_data["code"])) > 100:
        log_data["code"] = f"{str(log_data['code'])[:100]}... (truncated)"
    logger.info(f"User {user_id} sent scan request: {log_data}")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                PUBLIC_AI_API_URL,
                json=request_data,
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()

        logger.info(f"User {user_id} scan completed")
        return {"status": "success", "result": result, "user_id": user_id}

    except httpx.RequestError as e:
        logger.error(f"User {user_id} failed to call AI API: {str(e)}")
        raise HTTPException(status_code=500, detail="AI service unavailable")
    except httpx.HTTPStatusError as e:
        logger.error(f"User {user_id} AI API error: {e.response.status_code}")
        raise HTTPException(status_code=e.response.status_code, detail="AI service error")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)