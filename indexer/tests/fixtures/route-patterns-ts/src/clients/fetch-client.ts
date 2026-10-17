/**
 * Demo
 * DO NOT MODIFY - This file has been generated using oazapfts.
 */
import * as Oazapfts from "@oazapfts/runtime";
import * as QS from "@oazapfts/runtime/query";
export const defaults: Oazapfts.Defaults<Oazapfts.CustomHeaders> = {
    headers: {},
    baseUrl: "/api"
};
const oazapfts = Oazapfts.runtime(defaults);
export function getActivities({ albumId }: { albumId: string }, opts?: Oazapfts.RequestOpts) {
    return oazapfts.ok(oazapfts.fetchJson<{ status: 200 }>(`/activities${QS.query(QS.explode({ albumId }))}`, {
        ...opts
    }));
}
export function createActivity({ dto }: { dto: object }, opts?: Oazapfts.RequestOpts) {
    return oazapfts.ok(oazapfts.fetchJson<{ status: 201 }>("/activities", oazapfts.json({
        ...opts,
        method: "POST",
        body: dto
    })));
}
export function deleteActivity({ id }: { id: string }, opts?: Oazapfts.RequestOpts) {
    return oazapfts.ok(oazapfts.fetchText(`/activities/${encodeURIComponent(id)}`, {
        ...opts,
        method: "DELETE"
    }));
}
