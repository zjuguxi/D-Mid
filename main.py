from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
import httpx
import logging
import os
from typing import Optional, Dict
from pydantic import BaseModel
from datetime import timedelta
from auth import (
    User, Token, authenticate_user, create_access_token,
    get_current_active_user, ACCESS_TOKEN_EXPIRE_MINUTES
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="D-Mid Middleware",
    description="这是一个代码扫描中间件服务，用于连接用户和 AI 代码扫描服务。",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 模拟公共 AI API 地址
PUBLIC_AI_API_URL = os.getenv("PUBLIC_AI_API_URL", "https://api.example.com/scan")

# 请求模型
class ScanRequest(BaseModel):
    code: str
    language: str
    options: Optional[Dict] = None

    class Config:
        json_schema_extra = {
            "example": {
                "code": "def hello_world():\n    print('Hello, World!')",
                "language": "python",
                "options": {
                    "max_line_length": 80,
                    "check_style": True
                }
            }
        }

# 响应模型
class ScanResponse(BaseModel):
    status: str
    result: Dict
    user_id: str

    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "result": {
                    "issues": [],
                    "score": 95,
                    "suggestions": []
                },
                "user_id": "user1"
            }
        }

# 健康检查端点
@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "healthy"}

# 认证端点
@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """获取访问令牌"""
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# 代码扫描端点
@app.post("/scan", response_model=ScanResponse)
async def scan_code(
    request_data: ScanRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    代码扫描端点
    
    Args:
        request_data: 包含代码和扫描选项的请求数据
        current_user: 当前认证用户
        
    Returns:
        ScanResponse: 扫描结果
        
    Raises:
        HTTPException: 当扫描服务出错时
    """
    # 优化日志显示，避免显示大量数据
    log_data = request_data.model_dump()
    if "code" in log_data and len(str(log_data["code"])) > 100:
        log_data["code"] = f"{str(log_data['code'])[:100]}... (truncated)"
    logger.info(f"User {current_user.username} sent scan request: {log_data}")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                PUBLIC_AI_API_URL,
                json=request_data.model_dump(),
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()

        logger.info(f"User {current_user.username} scan completed")
        return {"status": "success", "result": result, "user_id": current_user.username}

    except httpx.RequestError as e:
        logger.error(f"User {current_user.username} failed to call AI API: {str(e)}")
        raise HTTPException(status_code=500, detail="AI service unavailable")
    except httpx.HTTPStatusError as e:
        logger.error(f"User {current_user.username} AI API error: {e.response.status_code}")
        raise HTTPException(status_code=e.response.status_code, detail="AI service error")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)