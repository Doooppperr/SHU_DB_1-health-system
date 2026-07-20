<template>
  <div class="workspace-page org-dashboard" v-loading="loading">
    <section class="org-hero">
      <div>
        <p class="org-kicker">今日运营工作台</p>
        <h2>{{ summary.institution?.name || "机构运营总览" }}</h2>
        <p class="org-hero-copy">先处理到检与待归档任务，再检查服务容量和套餐审核进度。</p>
      </div>
      <div class="org-hero-actions">
        <el-button type="primary" @click="goReports('today')">开始今日接待</el-button>
        <el-button @click="router.push({ name: 'org-packages' })">管理体检服务</el-button>
      </div>
    </section>

    <section class="org-overview-grid" aria-label="今日运营指标">
      <article v-for="metric in metrics" :key="metric.label" class="org-overview-card">
        <span class="org-overview-icon" aria-hidden="true">{{ metric.icon }}</span>
        <div>
          <small>{{ metric.label }}</small>
          <strong>{{ metric.value }}</strong>
          <p>{{ metric.note }}</p>
        </div>
      </article>
    </section>

    <section class="org-task-layout">
      <article class="org-panel">
        <header class="org-panel-header">
          <div><p class="org-kicker">优先处理</p><h3>今日任务</h3></div>
          <el-button link type="primary" @click="goReports('all')">查看全部</el-button>
        </header>
        <div class="org-task-list">
          <button v-for="task in tasks" :key="task.title" type="button" class="org-task" @click="task.action">
            <span class="org-task-mark" :class="task.tone">{{ task.icon }}</span>
            <span><strong>{{ task.title }}</strong><small>{{ task.description }}</small></span>
            <b>{{ task.count }}</b>
            <i aria-hidden="true">›</i>
          </button>
        </div>
      </article>

      <article class="org-panel org-guide">
        <p class="org-kicker">规范提醒</p>
        <h3>健康数据归档流程</h3>
        <ol>
          <li><span>1</span><div><strong>确认受检者已到检</strong><small>确认后用户将不能再取消预约。</small></div></li>
          <li><span>2</span><div><strong>录入并复核检查结果</strong><small>可添加指标、文字结论和检查影像。</small></div></li>
          <li><span>3</span><div><strong>锁定并提交归档</strong><small>归档后成为用户的正式健康数据。</small></div></li>
        </ol>
        <el-alert title="机构只能处理本机构预约，不可浏览用户个人测量或其他机构数据。" type="info" show-icon :closable="false" />
      </article>
    </section>

    <section v-if="recentReviews.length" class="org-panel">
      <header class="org-panel-header"><div><p class="org-kicker">平台反馈</p><h3>最近的套餐审核</h3></div><el-button link type="primary" @click="router.push({name:'org-package-reviews'})">查看审核记录</el-button></header>
      <div class="review-strip"><article v-for="review in recentReviews" :key="review.id"><el-tag :type="reviewTone(review.status)" size="small">{{reviewLabel(review.status)}}</el-tag><strong>{{review.package_name || review.name || '套餐变更'}}</strong><span>{{review.reason || review.review_note || review.comment || '平台已更新审核状态，请查看详情。'}}</span></article></div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";

import { fetchOrgDashboard } from "../../api/dashboards";

const router = useRouter();
const summary = ref({});
const loading = ref(false);

const appointmentCounts = computed(() => summary.value.appointment_status_counts || {});
const today = computed(() => summary.value.today || {});
const recentReviews = computed(() => summary.value.recent_package_reviews || []);
const metrics = computed(() => [
  { label: "今日已预约", value: today.value.booked ?? appointmentCounts.value.unfulfilled ?? 0, icon: "约", note: today.value.capacity ? `接待能力 ${today.value.capacity} 人` : "今日服务安排" },
  { label: "等待到检", value: today.value.awaiting_arrival ?? appointmentCounts.value.unfulfilled ?? 0, icon: "到", note: "需要核对身份并接待" },
  { label: "等待归档", value: today.value.awaiting_archive ?? appointmentCounts.value.awaiting_report ?? 0, icon: "档", note: "需要完成结果复核" },
  { label: "今日剩余名额", value: today.value.remaining ?? "不限", icon: "余", note: `${today.value.waitlist_subscriptions || 0} 人订阅空位提醒` },
]);
const tasks = computed(() => [
  { title: "确认今日到检", description: "核对身份并开始本次体检", count: today.value.awaiting_arrival ?? appointmentCounts.value.unfulfilled ?? 0, icon: "到", tone: "is-green", action: () => goReports("today") },
  { title: "完成待归档数据", description: "补充结果、检查影像并提交", count: today.value.awaiting_archive ?? appointmentCounts.value.awaiting_report ?? 0, icon: "档", tone: "is-orange", action: () => goReports("archive") },
  { title: "查看套餐审核反馈", description: "处理待审核或被退回的服务变更", count: summary.value.pending_package_review_count || 0, icon: "审", tone: "is-blue", action: () => router.push({ name: "org-package-reviews" }) },
]);
const reviewLabel=(status)=>({pending:"待审核",approved:"已通过",rejected:"需调整"}[status]||"已更新");
const reviewTone=(status)=>({pending:"warning",approved:"success",rejected:"danger"}[status]||"info");

function goReports(view) {
  router.push({ name: "org-reports", query: { view } });
}

onMounted(async () => {
  loading.value = true;
  try {
    summary.value = (await fetchOrgDashboard()).data.summary || {};
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || "运营数据加载失败");
  } finally {
    loading.value = false;
  }
});
</script>

<style scoped>
.org-dashboard { display: grid; gap: 18px; }
.org-hero { display:flex; align-items:center; justify-content:space-between; gap:24px; padding:28px; border:1px solid #dce8e6; border-radius:18px; background:linear-gradient(135deg,#f1faf7,#fff 72%); }
.org-hero h2,.org-panel h3 { margin:4px 0 8px; color:#173f42; }
.org-hero h2 { font-size:clamp(24px,3vw,34px); }
.org-kicker { margin:0; color:var(--workspace-accent); font-size:12px; font-weight:800; letter-spacing:.08em; }
.org-hero-copy { margin:0; color:#60777a; line-height:1.7; }
.org-hero-actions { display:flex; gap:10px; flex-wrap:wrap; }
.org-overview-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:14px; }
.org-overview-card { display:flex; gap:14px; padding:20px; border:1px solid #e0e9e7; border-radius:16px; background:#fff; }
.org-overview-icon,.org-task-mark { display:grid; place-items:center; flex:0 0 auto; border-radius:12px; color:#0a6d61; background:#e7f5f1; font-weight:800; }
.org-overview-icon { width:42px; height:42px; }
.org-overview-card small,.org-task small,.org-guide small { display:block; color:#758789; }
.org-overview-card strong { display:block; margin:4px 0; color:#173f42; font-size:26px; }
.org-overview-card p { margin:0; color:#758789; font-size:12px; }
.org-task-layout { display:grid; grid-template-columns:minmax(0,1.35fr) minmax(320px,.65fr); gap:18px; }
.org-panel { padding:22px; border:1px solid #e0e9e7; border-radius:16px; background:#fff; }
.org-panel-header { display:flex; align-items:center; justify-content:space-between; gap:12px; }
.org-task-list { display:grid; gap:10px; margin-top:12px; }
.org-task { display:grid; grid-template-columns:auto minmax(0,1fr) auto auto; align-items:center; gap:13px; width:100%; padding:14px; border:1px solid #e5eceb; border-radius:13px; color:#27484b; background:#fbfdfc; cursor:pointer; text-align:left; }
.org-task:hover { border-color:#8fc8bd; background:#f3faf8; }
.org-task-mark { width:38px; height:38px; }
.org-task-mark.is-orange { color:#986020; background:#fff2dd; }
.org-task-mark.is-blue { color:#356b9a; background:#eaf3fb; }
.org-task b { font-size:22px; }.org-task i { color:#789; font-size:24px; font-style:normal; }
.org-guide ol { display:grid; gap:15px; padding:0; list-style:none; }
.org-guide li { display:flex; gap:12px; }.org-guide li>span { display:grid; place-items:center; width:28px; height:28px; border-radius:50%; color:white; background:#2c8c7c; font-weight:800; }
.org-guide :deep(.el-alert) { margin-top:18px; }
.review-strip{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-top:12px}.review-strip article{display:grid;align-content:start;gap:7px;padding:14px;border:1px solid #e5eceb;border-radius:12px;background:#fbfdfc}.review-strip :deep(.el-tag){width:max-content}.review-strip strong{color:#2b4c4f}.review-strip span{color:#738587;font-size:12px;line-height:1.55}
@media(max-width:1100px){.org-overview-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.org-task-layout{grid-template-columns:1fr}}
@media(max-width:800px){.review-strip{grid-template-columns:1fr}}
@media(max-width:650px){.org-hero{align-items:flex-start;flex-direction:column;padding:20px}.org-hero-actions{width:100%}.org-hero-actions :deep(.el-button){flex:1}.org-overview-grid{grid-template-columns:1fr}.org-task{grid-template-columns:auto minmax(0,1fr) auto}.org-task i{display:none}}
:global(html[data-theme="dark"]) .org-hero,
:global(html[data-theme="dark"]) .org-overview-card,
:global(html[data-theme="dark"]) .org-panel,
:global(html[data-theme="dark"]) .org-task,
:global(html[data-theme="dark"]) .review-strip article{border-color:var(--color-border);color:var(--color-text);background:var(--color-surface)}
:global(html[data-theme="dark"]) .org-hero h2,
:global(html[data-theme="dark"]) .org-panel h3,
:global(html[data-theme="dark"]) .org-overview-card strong,
:global(html[data-theme="dark"]) .org-task{color:var(--color-text)}
</style>
