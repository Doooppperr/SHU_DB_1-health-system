import http from "./http";

export const fetchMeasurements = (params = {}) => http.get("/self-measurements", { params });
export const createMeasurement = (payload) => http.post("/self-measurements", payload);
export const updateMeasurement = (id, payload) => http.put(`/self-measurements/${id}`, payload);
export const deleteMeasurement = (id) => http.delete(`/self-measurements/${id}`);
export const fetchHealthDashboard = () => http.get("/health/dashboard");
export const fetchTimeline = (params = {}) => http.get("/health/timeline", { params });
export const fetchTrend = (indicatorId, params = {}) => http.get(`/health/trends/${indicatorId}`, { params });
export const fetchHealthDomains = () => http.get("/health-domains");
export const fetchHealthData = (params = {}) => http.get("/health-data", { params });
export const fetchHealthDataDetail = (id, params = {}) => http.get(`/health-data/${id}`, { params });
export const fetchHealthTrends = (domainId, params = {}) => http.get(`/health-trends/${domainId}`, { params });
export const fetchHealthAssetContent = (healthDataId, assetId, params = {}) => http.get(`/health-data/${healthDataId}/assets/${assetId}/content`, { params, responseType: "blob" });
