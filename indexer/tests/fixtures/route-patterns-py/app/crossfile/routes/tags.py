from fastapi import APIRouter

router = APIRouter()


@router.get("")  # the router's root: GET /api/v1/tags, the prefix comes with the include
def list_tags(): ...


@router.get("/{tag_id}")
def read_tag(tag_id: int): ...
