export const ROLE_USER = "user";
export const ROLE_INSTITUTION_ADMIN = "institution_admin";
export const ROLE_ADMIN = "admin";

export const ROLE_LABELS = {
  [ROLE_USER]: "普通用户",
  [ROLE_INSTITUTION_ADMIN]: "机构管理员",
  [ROLE_ADMIN]: "系统管理员",
};

export function dashboardRouteForRole(role) {
  if (role === ROLE_ADMIN) {
    return { name: "admin-dashboard" };
  }
  if (role === ROLE_INSTITUTION_ADMIN) {
    return { name: "org-dashboard" };
  }
  return { name: "dashboard" };
}

export function roleLabel(role) {
  return ROLE_LABELS[role] || "未知角色";
}
