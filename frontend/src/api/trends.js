import http from "./http";

export function fetchIndicatorTrend(indicatorDictId, ownerId) {
  return http.get(`/trends/indicators/${indicatorDictId}`, {
    params: { owner_id: ownerId },
  });
}
