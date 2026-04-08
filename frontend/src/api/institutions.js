import http from "./http";

export function fetchInstitutions() {
  return http.get("/institutions");
}

export function fetchInstitutionDetail(institutionId) {
  return http.get(`/institutions/${institutionId}`);
}

export function fetchInstitutionPackages(institutionId) {
  return http.get(`/institutions/${institutionId}/packages`);
}
