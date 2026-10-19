import requests from './requests';

export class AccountsService {
    public list() {
        return requests.get('/account');
    }

    public get(name: string) {
        return requests.get(`/account/${name}`).then(res => res.body);
    }

    public logout() {
        return requests.delete('/session');
    }

    public tokens(name: string) {
        return requests.post(`/account/${name}/token`).send({});
    }
}
