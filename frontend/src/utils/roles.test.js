import { describe, expect, it } from "vitest";

import {
  ROLE_ADMIN,
  ROLE_INSTITUTION_ADMIN,
  ROLE_USER,
  dashboardRouteForRole,
  roleLabel,
} from "./roles";

describe("role workspace helpers", () => {
  it.each([
    [ROLE_USER, "dashboard", "普通用户"],
    [ROLE_INSTITUTION_ADMIN, "org-dashboard", "机构管理员"],
    [ROLE_ADMIN, "admin-dashboard", "系统管理员"],
  ])("maps %s to its dedicated workspace", (role, routeName, label) => {
    expect(dashboardRouteForRole(role)).toEqual({ name: routeName });
    expect(roleLabel(role)).toBe(label);
  });

  it("falls back to the regular-user workspace for an unknown role", () => {
    expect(dashboardRouteForRole("unknown")).toEqual({ name: "dashboard" });
  });
});
