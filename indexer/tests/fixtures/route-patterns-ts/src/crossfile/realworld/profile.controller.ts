import { Router } from 'express';

export const profiles = Router();
profiles.get('/profiles/:username', getProfile);

function getProfile() {}
