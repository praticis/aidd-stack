from fastapi import APIRouter

from app.crossfile.routes import orders
from app.crossfile.routes.tags import router as tag_router

api_router = APIRouter()
api_router.include_router(orders.router)  # a router of an imported module
api_router.include_router(tag_router, prefix="/tags")  # a router imported by name
