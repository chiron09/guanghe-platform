# -*- coding: utf-8 -*-
"""FastAPI 应用入口。"""
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .database import Base, engine
from .routers import accounts, auth, commission, publish, works

# 建表
Base.metadata.create_all(bind=engine)

app = FastAPI(title="淘宝光合运营平台", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(accounts.router)
app.include_router(works.router)
app.include_router(commission.router)
app.include_router(publish.router)


@app.on_event("startup")
def _startup():
    publish.start_scheduler()
    accounts.start_auto_refresh_scheduler()


@app.get("/api/health")
def health():
    return {"status": "ok", "name": "淘宝光合运营平台"}


# 前端静态资源（构建产物）
_frontend_dist = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend", "dist")

if os.path.isdir(_frontend_dist):
    _assets_dir = os.path.join(_frontend_dist, "assets")
    if os.path.isdir(_assets_dir):
        app.mount("/assets", StaticFiles(directory=_assets_dir), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        """SPA fallback：非 /api 的路径回退到 index.html（支持 history 路由刷新）。"""
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        index = os.path.join(_frontend_dist, "index.html")
        if os.path.isfile(index):
            return FileResponse(index)
        raise HTTPException(status_code=404, detail="Not Found")

