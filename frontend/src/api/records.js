import http from "./http";

export function fetchRecords() {
  return http.get("/records");
}

export function createRecord(payload) {
  return http.post("/records", payload);
}

export function uploadRecordByOcr(formData) {
  return http.post("/records/upload", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });
}

export function confirmRecord(recordId) {
  return http.put(`/records/${recordId}/confirm`);
}

export function fetchRecordDetail(recordId) {
  return http.get(`/records/${recordId}`);
}

export function updateRecord(recordId, payload) {
  return http.put(`/records/${recordId}`, payload);
}

export function deleteRecord(recordId) {
  return http.delete(`/records/${recordId}`);
}

export function addRecordIndicator(recordId, payload) {
  return http.post(`/records/${recordId}/indicators`, payload);
}

export function updateRecordIndicator(recordId, indicatorId, payload) {
  return http.put(`/records/${recordId}/indicators/${indicatorId}`, payload);
}

export function deleteRecordIndicator(recordId, indicatorId) {
  return http.delete(`/records/${recordId}/indicators/${indicatorId}`);
}
