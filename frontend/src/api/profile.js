import http from "./http";

export const fetchProfile = () => http.get("/profile/me");
export const updateProfile = (payload) => http.put("/profile/me", payload);
