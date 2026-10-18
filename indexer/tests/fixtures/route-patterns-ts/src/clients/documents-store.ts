import { apiV2, client } from "./ApiClient";

export async function fetchDocuments() {
  await client.post("/documents.list", { limit: 25 }); // POST /api/documents.list
  await apiV2.post("/documents.info", { id: "x" }); // POST /api/v2/documents.info
}
