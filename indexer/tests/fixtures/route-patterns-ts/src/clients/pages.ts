import api from "@/clients/api-client";

export async function pageInfo(pageId: string) {
  const req = await api.post("/pages/info", { pageId }); // POST /api/pages/info: the base of another file's client
  return req.data;
}

export async function duplicatePage(pageId: string) {
  const req = await api.post<{ id: string }>("/pages/duplicate", { pageId }); // generic under await: POST /api/pages/duplicate
  return req.data;
}

export async function createPage(data: { title: string }) {
  const req = await api.post("/pages/create", data); // a client's call, whatever its last argument looks like
  return req.data;
}
