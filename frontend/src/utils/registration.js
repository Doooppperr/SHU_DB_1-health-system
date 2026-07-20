export function buildRegistrationPayload(mode, form) {
  const payload = {
    username: String(form.username || "").trim(),
    password: form.password || "",
    captcha_id: form.captcha_id || "",
    captcha_answer: String(form.captcha_answer || "").trim(),
  };

  const email = String(form.email || "").trim().toLowerCase();
  const phone = String(form.phone || "").trim();
  payload.email = email;
  if (phone) payload.phone = phone;

  if (mode === "staff") {
    const inviteCode = String(form.invite_code || "").trim();
    if (inviteCode) payload.invite_code = inviteCode;
  }

  return payload;
}
