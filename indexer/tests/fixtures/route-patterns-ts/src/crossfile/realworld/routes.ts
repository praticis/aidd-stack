// Routers of other files aggregated on an unnamed chain, exported under /api: GET /api/tags, GET /api/profiles/{username}.
import { Router } from 'express';
import tags from './tag.controller';
import { profiles } from './profile.controller';

const api = Router().use(tags).use(profiles);
export default Router().use('/api', api);
