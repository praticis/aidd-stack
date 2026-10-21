export async function accountDetails(id: string) {
  return fetch(`/api/accounts/${id}/details`);
}
