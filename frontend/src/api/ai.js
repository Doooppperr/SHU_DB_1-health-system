import http from "./http";


export function sendAiChat(payload) {
  return http.post("/ai/chat", payload, {
    timeout: 75000,
  });
}
