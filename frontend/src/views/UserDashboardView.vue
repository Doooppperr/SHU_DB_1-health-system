<template>
  <div class="workspace-page">
    <section class="welcome-panel welcome-panel--user">
      <div>
        <p>你好，{{ authStore.user?.username || "用户" }}</p>
        <h2>今天也一起关注长期健康变化</h2>
        <span>集中管理档案、核对指标，并从历次体检中发现值得持续观察的线索。</span>
      </div>
      <el-button type="primary" size="large" round @click="router.push({ name: 'record-upload' })">
        上传体检报告
      </el-button>
    </section>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" :closable="false" show-icon />

    <section class="metric-grid" v-loading="loading">
      <article v-for="metric in metrics" :key="metric.label" class="metric-card">
        <span class="metric-icon">{{ metric.icon }}</span>
        <div><small>{{ metric.label }}</small><strong>{{ metric.value }}</strong><p>{{ metric.note }}</p></div>
      </article>
    </section>

    <section class="dashboard-grid dashboard-grid--wide">
      <el-card class="dashboard-card" shadow="never">
        <template #header>
          <div class="card-heading">
            <div><h3>最近健康档案</h3><p>快速回到近期体检与指标</p></div>
            <el-button link type="primary" @click="router.push({ name: 'records' })">查看全部 →</el-button>
          </div>
        </template>
        <el-skeleton v-if="loading" :rows="4" animated />
        <el-empty v-else-if="recentRecords.length === 0" description="还没有健康档案">
          <el-button type="primary" @click="router.push({ name: 'records' })">新建第一份档案</el-button>
        </el-empty>
        <div v-else class="record-preview-list">
          <button
            v-for="record in recentRecords"
            :key="record.id"
            type="button"
            class="record-preview-item"
            @click="router.push({ name: 'record-detail', params: { id: record.id } })"
          >
            <span class="record-date"><strong>{{ dayOf(record.exam_date) }}</strong><small>{{ monthOf(record.exam_date) }}</small></span>
            <span class="record-preview-main">
              <strong>{{ record.institution?.name || "未关联机构" }}</strong>
              <small>{{ record.owner?.username || "本人" }} · {{ record.package?.name || "未选择套餐" }}</small>
            </span>
            <el-tag :type="record.status === 'confirmed' ? 'success' : 'warning'" effect="light">
              {{ statusText(record.status) }}
            </el-tag>
            <span class="record-count">{{ record.indicator_count || 0 }} 项</span>
          </button>
        </div>
      </el-card>

      <el-card class="dashboard-card" shadow="never">
        <template #header><div class="card-heading"><div><h3>快捷操作</h3><p>从常用任务开始</p></div></div></template>
        <div class="quick-action-list">
          <button v-for="action in quickActions" :key="action.name" type="button" @click="router.push({ name: action.name })">
            <span>{{ action.icon }}</span><div><strong>{{ action.title }}</strong><small>{{ action.description }}</small></div><b>→</b>
          </button>
        </div>
      </el-card>
    </section>

    <el-alert
      title="健康提示"
      description="趋势与 AI 内容用于健康科普参考，不能替代医生诊断；出现明显不适请及时就医。"
      type="info"
      show-icon
      :closable="false"
    />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { fetchUserDashboard } from "../api/dashboards";
import { useAuthStore } from "../stores/auth";

const router = useRouter();
const authStore = useAuthStore();
const loading = ref(false);
const errorMessage = ref("");
const summary = ref({});
const recentRecords = ref([]);

const metrics = computed(() => [
  { label: "健康档案", value: summary.value.record_count ?? 0, icon: "档", note: "本人及已授权亲友" },
  { label: "已确认档案", value: summary.value.confirmed_count ?? 0, icon: "确", note: "可用于趋势与 AI" },
  { label: "异常指标", value: summary.value.abnormal_indicator_count ?? 0, icon: "异", note: "建议持续关注" },
  { label: "最近体检", value: summary.value.recent_exam_date || "暂无", icon: "历", note: "最近一次检查日期" },
]);
const quickActions = [
  { name: "record-upload", icon: "OCR", title: "上传报告", description: "识别候选指标并核对入档" },
  { name: "records", icon: "新", title: "手工建档", description: "创建一份不依赖机构的档案" },
  { name: "trends", icon: "趋", title: "查看趋势", description: "按归属人与指标追踪变化" },
  { name: "friends", icon: "友", title: "亲友授权", description: "管理家人的档案协作权限" },
];

const dayOf = (date) => (date ? String(date).slice(8, 10) : "--");
const monthOf = (date) => (date ? `${String(date).slice(5, 7)}月` : "未知");
const statusText = (status) => ({ confirmed: "已确认", parsed: "待确认", draft: "草稿" }[status] || status || "未知");

async function loadDashboard() {
  loading.value = true;
  errorMessage.value = "";
  try {
    const { data } = await fetchUserDashboard();
    summary.value = data.summary || {};
    recentRecords.value = data.recent_records || [];
  } catch (error) {
    errorMessage.value = error?.response?.data?.message || "健康总览加载失败";
  } finally {
    loading.value = false;
  }
}

onMounted(loadDashboard);
</script>
