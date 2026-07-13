import http from "./http";

export function fetchAdminInstitutions() {
  return http.get("/admin/institutions");
}

export function createAdminInstitution(payload) {
  return http.post("/admin/institutions", payload);
}

export function fetchAdminInstitution(institutionId) {
  return http.get(`/admin/institutions/${institutionId}`);
}

export function updateAdminInstitution(institutionId, payload) {
  return http.put(`/admin/institutions/${institutionId}`, payload);
}

export function deactivateAdminInstitution(institutionId) {
  return http.post(`/admin/institutions/${institutionId}/deactivate`);
}

export function restoreAdminInstitution(institutionId) {
  return http.post(`/admin/institutions/${institutionId}/restore`);
}

export function fetchAdminPackages(institutionId) {
  return http.get(`/admin/institutions/${institutionId}/packages`);
}

export function createAdminPackage(institutionId, payload) {
  return http.post(`/admin/institutions/${institutionId}/packages`, payload);
}

export function updateAdminPackage(institutionId, packageId, payload) {
  return http.put(`/admin/institutions/${institutionId}/packages/${packageId}`, payload);
}

export function deactivateAdminPackage(institutionId, packageId) {
  return http.delete(`/admin/institutions/${institutionId}/packages/${packageId}`);
}

export function fetchAdminImages(institutionId) {
  return http.get(`/admin/institutions/${institutionId}/images`);
}

export function uploadAdminImage(institutionId, file) {
  const formData = new FormData();
  formData.append("file", file);
  return http.post(`/admin/institutions/${institutionId}/images`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
}

export function reorderAdminImages(institutionId, imageIds) {
  return http.put(`/admin/institutions/${institutionId}/images/order`, { image_ids: imageIds });
}

export function deleteAdminImage(institutionId, imageId) {
  return http.delete(`/admin/institutions/${institutionId}/images/${imageId}`);
}

export function fetchAdminInvites() {
  return http.get("/admin/invites");
}

export function fetchInstitutionInvite(institutionId) {
  return http.get(`/admin/institutions/${institutionId}/invite`);
}

export function issueInstitutionInvite(institutionId) {
  return http.post(`/admin/institutions/${institutionId}/invite`);
}

export function revokeInstitutionInvite(institutionId) {
  return http.delete(`/admin/institutions/${institutionId}/invite`);
}

export function revokeInstitutionAdmin(userId) {
  return http.post(`/admin/users/${userId}/revoke-institution-admin`);
}

export function fetchAdminRecords(params = {}) {
  return http.get("/admin/records", { params });
}

export function createAdminRecord(payload) {
  return http.post("/admin/records", payload);
}

export function fetchAdminRecord(recordId) {
  return http.get(`/admin/records/${recordId}`);
}

export function updateAdminRecord(recordId, payload) {
  return http.put(`/admin/records/${recordId}`, payload);
}

export function deleteAdminRecord(recordId) {
  return http.delete(`/admin/records/${recordId}`);
}

export function addAdminRecordIndicator(recordId, payload) {
  return http.post(`/admin/records/${recordId}/indicators`, payload);
}

export function updateAdminRecordIndicator(recordId, indicatorId, payload) {
  return http.put(`/admin/records/${recordId}/indicators/${indicatorId}`, payload);
}

export function deleteAdminRecordIndicator(recordId, indicatorId) {
  return http.delete(`/admin/records/${recordId}/indicators/${indicatorId}`);
}
