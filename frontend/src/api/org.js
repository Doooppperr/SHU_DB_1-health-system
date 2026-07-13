import http from "./http";

export function fetchOrgInstitution() {
  return http.get("/org/institution");
}

export function updateOrgInstitution(payload) {
  return http.put("/org/institution", payload);
}

export function fetchOrgPackages() {
  return http.get("/org/packages");
}

export function createOrgPackage(payload) {
  return http.post("/org/packages", payload);
}

export function updateOrgPackage(packageId, payload) {
  return http.put(`/org/packages/${packageId}`, payload);
}

export function deactivateOrgPackage(packageId) {
  return http.delete(`/org/packages/${packageId}`);
}

export function fetchOrgImages() {
  return http.get("/org/images");
}

export function uploadOrgImage(file) {
  const formData = new FormData();
  formData.append("file", file);
  return http.post("/org/images", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
}

export function reorderOrgImages(imageIds) {
  return http.put("/org/images/order", { image_ids: imageIds });
}

export function deleteOrgImage(imageId) {
  return http.delete(`/org/images/${imageId}`);
}

export function fetchOrgHealthRecords(params = {}) {
  return http.get("/institution-health/records", { params });
}

export function fetchOrgHealthRecord(recordId) {
  return http.get(`/institution-health/records/${recordId}`);
}

export function fetchOrgHealthTrends(params) {
  return http.get("/institution-health/trends", { params });
}
