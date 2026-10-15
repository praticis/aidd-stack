from fastapi import APIRouter

router = APIRouter(prefix="/items")


@router.get("/")  # the router root, its prefix known: GET /items
def list_items():
    return []


@router.get("/{item_id}")
def get_item(item_id: int):
    return {}
