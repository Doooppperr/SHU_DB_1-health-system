import { describe, expect, it } from "vitest";
import { normalizeApiMessage } from "./apiMessages";

describe("public API message normalization", () => {
  it("uses stable business codes and never leaks English validation text", () => {
    expect(normalizeApiMessage("constraint failed", "APPOINTMENT_DATE_CONFLICT")).toContain("当天已有预约");
    expect(normalizeApiMessage("participant_user_ids must be an array")).toBe("操作没有完成，请稍后重试");
    expect(normalizeApiMessage("机构已停用")).toBe("机构已停用");
  });
});
