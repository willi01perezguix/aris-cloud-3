from fastapi import APIRouter

from app.aris3.routers.health import router as health_router
from app.aris3.routers.auth import router as auth_router
from app.aris3.routers.users import router as users_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router, prefix="/aris3/auth", tags=["auth"])
api_router.include_router(users_router, prefix="/aris3", tags=["users"])
