import http from "./http";

export function fetchFriends() {
  return http.get("/friends");
}

export function addFriend(payload) {
  return http.post("/friends", payload);
}

export function renameFriend(relationId, payload) {
  return http.put(`/friends/${relationId}`, payload);
}

export function updateFriendAuthorization(relationId, payload) {
  return http.put(`/friends/${relationId}/authorization`, payload);
}

export function deleteFriend(relationId) {
  return http.delete(`/friends/${relationId}`);
}
