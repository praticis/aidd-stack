from aiohttp import web


def setup_routes(app: web.Application) -> None:
    app.router.add_view("/", IndexView)  # the application router: its root is a route
    app.router.add_get("/polls", index)
    app.router.add_post("/poll/{question_id}/vote", vote, name="vote")
    add_route = app.router.add_route
    add_route("*", "/graphql", graphql)
    add_route("POST", "/predict", predict)
    app.router.add_static("/static/", "static")  # files, not a route


class FlagApi:
    def __init__(self, http) -> None:
        self._http = http

    def configuration(self, body: str):
        return self._http.request(method="POST", url="/v1/flag/configuration", body=body)  # method as a keyword


class IndexView(web.View): ...


async def index(request): ...
async def vote(request): ...
async def graphql(request): ...
async def predict(request): ...
