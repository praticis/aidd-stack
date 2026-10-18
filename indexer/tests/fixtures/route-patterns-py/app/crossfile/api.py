from fastapi import APIRouter

from app.crossfile.routes import admin, audits, orders, recipes, timeline
from app.crossfile.routes.tags import router as tag_router

api_router = APIRouter()
api_router.include_router(orders.router)  # a router of an imported module
api_router.include_router(tag_router, prefix="/tags")  # a router imported by name
api_router.include_router(recipes.router)  # the project's router classes (routers.py)
api_router.include_router(timeline.router, prefix="/recipes")
api_router.include_router(admin.router)
api_router.include_router(audits.router)
