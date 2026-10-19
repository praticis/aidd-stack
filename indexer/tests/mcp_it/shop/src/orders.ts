export async function loadOrder(id: string) {
  return fetch(`/v1/orders/${id}`);
}
