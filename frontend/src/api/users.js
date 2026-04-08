import http from "./http";

export function fetchUsers() {
  return http.get("/users");
}

export function updateUser(userId, payload) {
  return http.put(`/users/${userId}`, payload);
}

export function deleteUser(userId) {
  return http.delete(`/users/${userId}`);
}
