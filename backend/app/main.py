from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app import seed
from app.modules import 发射冻结戳
from app.routers import api

app = FastAPI(title="播浪", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
def _启动():
    seed.初始化库()


@app.exception_handler(发射冻结戳.缺戳异常)
async def _缺戳整票拒绝(_请求, 异常: 发射冻结戳.缺戳异常):
    """甲口径：同窗准时写缺有效冻结戳 → 整票拒绝（装载事务已整体回滚）。"""
    return JSONResponse(
        status_code=409,
        content={"detail": str(异常), "命运": "整票拒绝", "口径": 发射冻结戳.口径},
    )


app.include_router(api)
