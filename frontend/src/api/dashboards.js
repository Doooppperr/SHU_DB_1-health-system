import http from "./http";

export function fetchUserDashboard() {
  return http.get("/records/summary");
}

export function fetchOrgDashboard() {
  return http.get("/org/dashboard");
}

export function fetchAdminDashboard() {
  return http.get("/admin/dashboard");
}
