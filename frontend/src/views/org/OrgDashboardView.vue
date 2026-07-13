<template>
  <div class="workspace-page">
    <section class="welcome-panel welcome-panel--org">
      <div>
        <p>机构运营工作台</p>
        <h2>{{ institutionName }}</h2>
        <span>维护公开服务信息，并在严格脱敏和只读范围内了解本机构体检数据。</span>
      </div>
      <el-tag :type="institutionActive ? 'success' : 'danger'" size="large" effect="dark">
        {{ institutionActive ? "正常运营" : "机构已停用" }}
      </el-tag>
    </section>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon :closable="false" />

    <section class="metric-grid" v-loading="loading">
      <article v-for="metric in metrics" :key="metric.label" class="metric-card">
        <span class="metric-icon">{{ metric.icon }}</span>
        <div><small>{{ metric.label }}</small><strong>{{ metric.value }}</strong><p>{{ metric.note }}</p></div>
      </article>
    </section>

    <section class="dashboard-grid dashboard-grid--wide">
      <el-card class="dashboard-card" shadow="never">
        <template #header>
          <div class="card-heading"><div><h3>最近确认档案</h3><p>仅展示来源于本机构的脱敏数据</p></div><el-button link type="primary" @click="router.push({ name: 'org-records' })">查看全部 →</el-button></div>
        </template>
        <el-empty v-if="!loading && recentRecords.length === 0" description="暂无可查看的已确认档案" />
        <el-table v-else :data="recentRecords" v-loading="loading" class="clean-table">
          <el-table-column prop="exam_date" label="体检日期" width="120" />
          <el-table-column label="归属人" min-width="120">
            <template #default="scope">{{ scope.row.owner_display_name || scope.row.owner?.display_name || scope.row.owner?.username || `用户 ${scope.row.owner_id}` }}</template>
          </el-table-column>
          <el-table-column label="套餐" min-width="160">
            <template #default="scope">{{ scope.row.package?.name || "未选择套餐" }}</template>
          </el-table-column>
          <el-table-column prop="indicator_count" label="指标数" width="90" />
          <el-table-column label="异常" width="90">
            <template #default="scope"><el-tag :type="scope.row.abnormal_count ? 'danger' : 'success'">{{ scope.row.abnormal_count || 0 }}</el-tag></template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card class="dashboard-card" shadow="never">
        <template #header><div class="card-heading"><div><h3>运营快捷入口</h3><p>维护机构对外展示内容</p></div></div></template>
        <div class="quick-action-list">
          <button v-for="action in actions" :key="action.name" type="button" @click="router.push({ name: action.name })">
            <span>{{ action.icon }}</span><div><strong>{{ action.title }}</strong><small>{{ action.description }}</small></div><b>→</b>
          </button>
        </div>
      </el-card>
    </section>

    <el-alert
      title="只读健康数据边界"
      description="你只能查看来源于本机构且已确认的标准化档案和指标；联系方式、上传人资料与原始报告不会开放，也不能修改用户健康数据。"
      type="warning"
      show-icon
      :closable="false"
    />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { fetchOrgDashboard } from "../../api/dashboards";

const router = useRouter();
const loading = ref(false);
const errorMessage = ref("");
const summary = ref({});
const recentRecords = ref([]);
const institutionName = computed(() => {
  const item = summary.value.institution;
  if (!item) return "我的机构";
  return [item.name, item.branch_name].filter(Boolean).join(" · ");
});
const institutionActive = computed(() => summary.value.institution?.is_active !== false);
const metrics = computed(() => [
  { label: "资料完整度", value: `${summary.value.profile_completion ?? 0}%`, icon: "资", note: "完善资料提升展示效果" },
  { label: "机构相册", value: `${summary.value.image_count ?? 0}/${summary.value.image_limit ?? 8}`, icon: "图", note: "首图自动作为封面" },
  { label: "启用套餐", value: summary.value.active_package_count ?? 0, icon: "套", note: "当前可展示套餐" },
  { label: "已确认档案", value: summary.value.confirmed_record_count ?? 0, icon: "档", note: `${summary.value.owner_count ?? 0} 位归属人` },
]);
const actions = [
  { name: "org-profile", icon: "资", title: "完善机构资料", description: "维护地址、电话和服务说明" },
  { name: "org-gallery", icon: "图", title: "管理机构相册", description: "上传、排序与设置封面" },
  { name: "org-packages", icon: "套", title: "维护体检套餐", description: "新增、编辑或停用套餐" },
  { name: "org-trends", icon: "趋", title: "查看机构趋势", description: "按归属人和指标筛选" },
];

async function loadDashboard() {
  loading.value = true;
  try {
    const { data } = await fetchOrgDashboard();
    summary.value = data.summary || {};
    recentRecords.value = data.recent_records || [];
  } catch (error) {
    errorMessage.value = error?.response?.data?.message || "机构运营总览加载失败";
  } finally {
    loading.value = false;
  }
}
onMounted(loadDashboard);
</script>
