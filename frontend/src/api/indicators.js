import http from "./http";

export function fetchIndicatorDicts(keyword = "") {
  const query = keyword ? `?keyword=${encodeURIComponent(keyword)}` : "";
  return http.get(`/indicators/dicts${query}`);
}
