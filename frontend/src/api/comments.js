import http from "./http";

export function fetchInstitutionComments(institutionId) {
  return http.get("/comments", {
    params: { institution_id: institutionId },
  });
}

export function fetchMyComments(params = {}) {
  return http.get("/comments/mine", { params });
}

export function createInstitutionComment(payload) {
  return http.post("/comments", payload);
}

export function fetchCommentModerationList() {
  return http.get("/comments/moderation");
}

export function updateCommentVisibility(commentId, payload) {
  return http.put(`/comments/${commentId}/visibility`, payload);
}

export function updateComment(commentId, payload) {
  return http.put(`/comments/${commentId}`, payload);
}

export function deleteComment(commentId) {
  return http.delete(`/comments/${commentId}`);
}
