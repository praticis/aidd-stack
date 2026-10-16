from flask_restx import Namespace, Resource

# flask-restx (CTFd's API): a Resource class per path, one route per HTTP method it defines; the namespace's path
# comes from add_namespace in another module, under the blueprint the Api is built on.
challenges_namespace = Namespace("challenges", description="Endpoint to retrieve Challenges")


def admins_only(f):
    return f


@challenges_namespace.route("")
class ChallengeList(Resource):
    def get(self):
        return []

    @admins_only
    def post(self):
        return {}


@challenges_namespace.route("/<challenge_id>")
class Challenge(Resource):
    def get(self, challenge_id):
        return {}

    def patch(self, challenge_id):
        return {}

    def serialize(self):  # not an HTTP method: no route
        return {}
