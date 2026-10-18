from app.crossfile.routers import UserAPIRouter

router = UserAPIRouter(["timeline"], "/timeline/events")  # the prefix by position, as UserAPIRouter.__init__ declares it


@router.post("")  # POST /api/v1/recipes/timeline/events: included under /recipes
def create_event(): ...
