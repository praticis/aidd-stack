from fastapi import APIRouter

router = APIRouter(prefix="/orders")


@router.get("/{order_id}")  # GET /api/v1/orders/{order_id}: included by api.py, mounted by main.py
def read_order(order_id: int): ...
