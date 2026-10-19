import * as path from 'path';
import * as agent from 'superagent';

let baseHRef = '/';

function toAbsURL(val: string): string {
    return path.join(baseHRef, val);
}

function apiRoot(): string {
    return toAbsURL('/api/v1');
}

function withHandlers(req: agent.Request) {
    return req;
}

// an object of request methods, each under the API root: the callers' paths are under it
export default {
    setBaseHRef(val: string) {
        baseHRef = val;
    },
    get(url: string) {
        return withHandlers(agent.get(`${apiRoot()}${url}`));
    },
    post(url: string) {
        return withHandlers(agent.post(`${apiRoot()}${url}`)).set('Content-Type', 'application/json');
    },
    delete(url: string) {
        return withHandlers(agent.del(`${apiRoot()}${url}`));
    },
};
