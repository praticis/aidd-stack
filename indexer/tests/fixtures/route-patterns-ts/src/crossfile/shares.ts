import express from "express";
import { validateBatch } from "./middleware";

const UUID_REGEX = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}";
const router = express.Router();

function searchShares() {}
function readShare() {}
function shareInfo() {}
function searchByKind() {}

router.search("/", validateBatch, searchShares); // Express's SEARCH verb: SEARCH /shares, a middleware of another file first
router.search("/:kind", validateBatch, searchByKind); // not a mount wrapper: SEARCH /shares/{kind}
router.get(`/:pk(${UUID_REGEX})`, readShare); // a constraint after the parameter, interpolated: GET /shares/{pk}
router.get("/info/:pk(\\d+)", shareInfo); // and written: GET /shares/info/{pk}

const app = express();
app.use("/shares", router);
