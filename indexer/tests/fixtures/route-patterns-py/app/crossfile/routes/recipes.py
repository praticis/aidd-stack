from app.crossfile.routers import UserAPIRouter

router = UserAPIRouter(prefix="/recipes")  # the project's APIRouter subclass, from another module


@router.get("")  # GET /api/v1/recipes: the root of a router with a prefix of its own
def list_recipes(): ...


@router.get("/{slug}/exports")
def export_recipe(slug: str): ...
