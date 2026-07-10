export const AI_SESSION_PREFIX = "health-ai-session:";


export function clearAllAiSessionStorage() {
  const keys = [];
  for (let index = 0; index < sessionStorage.length; index += 1) {
    const key = sessionStorage.key(index);
    if (key?.startsWith(AI_SESSION_PREFIX)) {
      keys.push(key);
    }
  }
  keys.forEach((key) => sessionStorage.removeItem(key));
}
