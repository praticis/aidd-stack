import { Router } from 'express';

const router = Router();
router.get('/tags', listTags);
export default router;

function listTags() {}
