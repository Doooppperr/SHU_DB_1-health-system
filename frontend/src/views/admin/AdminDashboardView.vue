<template>
  <div class="workspace-page">
    <section class="welcome-panel welcome-panel--admin">
      <div>
        <p>平台治理中心</p>
        <h2>系统运行概览</h2>
        <span>从角色、机构、档案与内容审核四个维度掌握平台状态。</span>
      </div>
      <span class="admin-shield">ADMIN</span>
    </section>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon :closable="false" />
    <section class="metric-grid" v-loading="loading">
      <article v-for="metric in metrics" :key="metric.label" class="metric-card">
        <span class="metric-icon">{{ metric.icon }}</span>
        <div><small>{{ metric.label }}</small><strong>{{ metric.value }}</strong><p>{{ metric.note }}</p></div>
      </article>
    </section>

    <section class="dashboard-grid dashboard-grid--equal">
      <el-card class="dashboard-card" shadow="never">
        <template #header><div class="card-heading"><div><h3>角色分布</h3><p>当前账号角色构成</p></div></div></template>
        <div class="role-distribution">
          <div v-for="role in roles" :key="role.label">
            <span :class="role.className" /><p><strong>{{ role.value }}</strong><small>{{ role.label }}</small></p>
          </div>
        </div>
      </el-card>
      <el-card class="dashboard-card" shadow="never">
        <template #header><div class="card-heading"><div><h3>待办关注</h3><p>需要平台管理员处理的事项</p></div></div></template>
        <div class="admin-todo-list">
          <button type="button" @click="router.push({ name: 'admin-comments' })"><span>评</span><p><strong>{{ valueOf('pending_comment_count', 'pending_comments') }} 条评论待审核</strong><small>审核公开展示内容</small></p><b>→</b></button>
          <button type="button" @click="router.push({ name: 'admin-invites' })"><span>邀</span><p><strong>{{ inviteCounts.active ?? 0 }} 个有效邀请码</strong><small>管理机构管理员入驻</small></p><b>→</b></button>
          <button type="button" @click="router.push({ name: 'admin-institutions' })"><span>院</span><p><strong>{{ valueOf('inactive_institution_count') }} 家停用机构</strong><small>查看机构运营状态</small></p><b>→</b></button>
        </div>
      </el-card>
    </section>

    <section class="admin-shortcut-grid">
      <button v-for="action in shortcuts" :key="action.name" type="button" @click="router.push({ name: action.name })">
        <span>{{ action.icon }}</span><div><strong>{{ action.title }}</strong><small>{{ action.description }}</small></div><b>→</b>
      </button>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { fetchAdminDashboard } from "../../api/dashboards";

const router = useRouter();
const loading = ref(false);
const errorMessage = ref("");
const summary = ref({});
const valueOf = (...keys) => {
  for (const key of keys) if (summary.value[key] !== undefined) return summary.value[key];
  return 0;
};
const roleCounts = computed(() => summary.value.user_role_counts || summary.value.role_counts || summary.value.users_by_role || {});
const inviteCounts = computed(() => summary.value.invite_status_counts || {});
const metrics = computed(() => [
  { label: "用户总数", value: valueOf("user_count", "total_user_count", "total_users"), icon: "用", note: "全部注册账号" },
  { label: "启用机构", value: valueOf("active_institution_count", "active_institutions"), icon: "院", note: `停用 ${valueOf("inactive_institution_count", "inactive_institutions")} 家` },
  { label: "健康档案", value: valueOf("record_count", "total_record_count", "total_records"), icon: "档", note: `已确认 ${valueOf("confirmed_record_count", "confirmed_records")} 份` },
  { label: "待审评论", value: valueOf("pending_comment_count", "pending_comments"), icon: "评", note: "请及时处理" },
]);
const roles = computed(() => [
  { label: "普通用户", value: roleCounts.value.user ?? 0, className: "role-dot--user" },
  { label: "机构管理员", value: roleCounts.value.institution_admin ?? 0, className: "role-dot--org" },
  { label: "系统管理员", value: roleCounts.value.admin ?? 0, className: "role-dot--admin" },
]);
const shortcuts = [
  { name: "admin-institutions", icon: "院", title: "机构与套餐", description: "新建、停用、恢复机构及管理套餐" },
  { name: "admin-invites", icon: "邀", title: "邀请码管理", description: "签发、撤销并查看邀请码状态" },
  { name: "admin-users", icon: "用", title: "用户与角色", description: "查看角色并撤销机构管理员" },
  { name: "admin-records", icon: "档", title: "全局档案监管", description: "通过专属接口监管平台档案" },
];

async function loadDashboard() {
  loading.value = true;
  try {
    const { data } = await fetchAdminDashboard();
    summary.value = data.summary || data || {};
  } catch (error) {
    errorMessage.value = error?.response?.data?.message || "系统总览加载失败";
  } finally {
    loading.value = false;
  }
}
onMounted(loadDashboard);
</script>
