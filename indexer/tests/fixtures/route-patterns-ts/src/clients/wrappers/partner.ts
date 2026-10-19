import axios from 'axios';

const BASE = '/partner/v2';

// the rest of the path is the caller's; the verb is a parameter
export class PartnerClient {
  send(method: string, path: string) {
    return axios.request({ method, url: `${BASE}${path}` });
  }

  orders() {
    return this.send('GET', '/orders');
  }

  cancel(id: string) {
    return this.send('POST', `/orders/${id}/cancel`);
  }
}

const partner = new PartnerClient();

export function refund(id: string) {
  return partner.send('DELETE', `/orders/${id}`);
}

// counterexamples: a parameter as one segment is the call's own; a function of the file that is no wrapper
export function invoice(id: string) {
  return axios.get(`/billing/invoices/${id}`);
}

function track(event: string) {
  console.log(event);
}

track('/metrics/sent');
invoice('42');
