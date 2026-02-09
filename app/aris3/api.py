from fastapi import APIRouter

from app.aris3.routers.access_control import router as access_control_router
from app.aris3.routers.admin import router as admin_router
from app.aris3.routers.health import router as health_router
from app.aris3.routers.auth import router as auth_router
from app.aris3.routers.users import router as users_router
from app.aris3.routers.stock import router as stock_router
from app.aris3.routers.transfers import router as transfers_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router, prefix="/aris3/auth", tags=["auth"])
api_router.include_router(users_router, prefix="/aris3", tags=["users"])
api_router.include_router(access_control_router, prefix="/aris3/access-control", tags=["access-control"])
api_router.include_router(admin_router, prefix="/aris3/admin", tags=["admin"])
api_router.include_router(stock_router, tags=["stock"])
api_router.include_router(transfers_router, tags=["transfers"])
