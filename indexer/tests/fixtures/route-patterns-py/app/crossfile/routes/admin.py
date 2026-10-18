from app.crossfile import routers

router = routers.AdminAPIRouter(prefix="/admin")  # a subclass of a subclass, named through its module


@router.delete("/users/{user_id}")
def delete_user(user_id: int): ...
