const qs = require('querystring');

function signed(method, body) {
  return { method, body };
}

// the verb wrappers hand `_fetch` their options in a local; `_get` glues the query string to the path
class Ledger {
  async _fetch(url, options) {
    const res = await fetch(url, options);
    return res.json();
  }

  _host() {
    return process.env.LEDGER_URL;
  }

  async _get(endpoint, variables = false) {
    const init = { method: 'GET', headers: {} };
    return this._fetch(this._host() + endpoint + (variables ? '?' + qs.stringify(variables) : ''), init);
  }

  async _postJSON(endpoint, variables = {}) {
    const init = { ...this.defaults, method: 'POST', body: JSON.stringify(variables) };
    return this._fetch(this._host() + endpoint, init);
  }

  async _deleteRAW(endpoint) {
    const init = { ...this.defaults, method: 'DELETE' };
    return await this._fetch(this._host() + endpoint, init);
  }

  // options it cannot read: the verb is unknown, not fetch's GET
  async _putSigned(endpoint, body) {
    return this._fetch(this._host() + endpoint, signed('PUT', body));
  }

  balance() {
    return this._get('/ledger/v1/balance');
  }

  statements(params) {
    return this._get('/ledger/v1/statements', params);
  }

  pay(body) {
    return this._postJSON('/ledger/v1/payments', body);
  }

  cancel(id) {
    return this._deleteRAW(`/ledger/v1/payments/${id}`);
  }

  rename(body) {
    return this._putSigned('/ledger/v1/accounts/name', body);
  }
}

module.exports = Ledger;
