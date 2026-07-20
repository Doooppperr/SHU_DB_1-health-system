<template>
  <div class="workspace-page user-platform-page">
    <section class="user-page-lead">
      <div>
        <span class="user-kicker">长期变化</span>
        <h2>看看身体在一段时间里的变化</h2>
        <p>同一指标按来源分开呈现，既能看到日常习惯，也不会把机构检查和个人测量混为一谈。</p>
      </div>
      <el-button type="primary" @click="router.push({ name: 'dashboard', query: { quick: 'measurement' } })">记录新测量</el-button>
    </section>

    <el-card shadow="never" class="user-panel user-filter-panel">
      <div class="trend-filter-grid-platform">
        <label class="filter-field">
          <span class="filter-field-label">查看谁的趋势</span>
          <el-select v-model="filters.owner_id">
            <el-option v-for="owner in owners" :key="String(owner.value)" :label="owner.label" :value="owner.value" />
          </el-select>
        </label>
        <label class="filter-field">
          <span class="filter-field-label">健康方向</span>
          <el-select v-model="filters.domain_id" placeholder="选择健康方向">
            <el-option v-for="domain in domains" :key="domain.id" :label="domain.name" :value="domain.id" />
          </el-select>
        </label>
        <label class="filter-field">
          <span class="filter-field-label">日期范围</span>
          <el-date-picker v-model="dateRange" type="daterange" value-format="YYYY-MM-DD" range-separator="至" />
        </label>
        <div class="filter-actions"><el-button type="primary" @click="apply">查看变化</el-button></div>
      </div>
    </el-card>

    <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon />

    <section v-loading="loading" class="trend-story-grid" aria-live="polite">
      <article v-for="entry in series" :key="entry.indicator.id" class="trend-story-card">
        <header>
          <div><span>健康指标</span><h3>{{ entry.indicator.name }}</h3></div>
          <small>{{ entry.indicator.unit || "无单位" }}</small>
        </header>

        <section v-for="track in entry.series" :key="track.source_key" class="trend-source-story">
          <div class="trend-source-story__heading">
            <el-tag :type="track.source.type === 'self' ? 'info' : 'success'" effect="light">{{ sourceName(track.source) }}</el-tag>
            <div>
              <span>最近一次</span>
              <strong>{{ compact(track.summary.latest) }} <small>{{ entry.indicator.unit }}</small></strong>
            </div>
            <div>
              <span>较上次</span>
              <strong :class="changeClass(track.summary.change)">{{ changeLabel(track.summary.change) }}</strong>
            </div>
          </div>

          <div class="trend-chart-platform">
            <svg viewBox="0 0 360 150" preserveAspectRatio="none" role="img" :aria-label="`${entry.indicator.name}，${sourceName(track.source)}，共 ${track.summary.count} 次记录`">
              <line x1="12" y1="126" x2="348" y2="126" class="trend-chart-platform__axis" />
              <line x1="12" y1="76" x2="348" y2="76" class="trend-chart-platform__guide" />
              <polyline :points="sparkline(track.points)" class="trend-chart-platform__line" />
              <circle v-for="(point, index) in chartPoints(track.points)" :key="`${point.date}-${index}`" :cx="point.x" :cy="point.y" r="4" class="trend-chart-platform__point">
                <title>{{ point.date }}：{{ point.value }} {{ entry.indicator.unit }}</title>
              </circle>
            </svg>
            <div class="trend-chart-platform__range">
              <span>{{ formatShortDate(track.points[0]?.date) }}</span>
              <span>{{ track.summary.count }} 次记录</span>
              <span>{{ formatShortDate(track.points.at(-1)?.date) }}</span>
            </div>
          </div>
        </section>
      </article>
    </section>

    <el-card v-if="assetEvents.length" shadow="never" class="user-panel trend-asset-panel">
      <template #header><div class="user-section-heading"><div><span>检查附件</span><h3>这段时间的影像与文件</h3></div></div></template>
      <div class="trend-asset-list">
        <button v-for="event in assetEvents" :key="event.asset.id" type="button" @click="openAsset(event)">
          <span class="health-asset-grid__icon">{{ event.asset.modality === "pdf" ? "PDF" : "影" }}</span>
          <span><strong>{{ event.asset.title }}</strong><small>{{ sourceName(event.source) }} · {{ formatShortDate(event.date) }}</small></span>
          <span aria-hidden="true">›</span>
        </button>
      </div>
    </el-card>

    <div v-if="!loading && !series.length && !assetEvents.length" class="user-empty-state user-empty-state--page">
      <span class="user-empty-state__icon">趋</span>
      <div><strong>这个健康方向还没有足够的数据</strong><p>连续记录几次后，就能在这里看见自己的变化。</p></div>
      <el-button type="primary" plain @click="router.push({ name: 'dashboard', query: { quick: 'measurement' } })">开始记录</el-button>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { useRoute, useRouter } from "vue-router";
import { fetchFriends } from "../api/friends";
import { fetchHealthAssetContent, fetchHealthDomains, fetchHealthTrends } from "../api/health";
import { useAuthStore } from "../stores/auth";
import { buildHealthOwnerOptions } from "../utils/healthOwners";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const domains = ref([]);
const owners = ref([]);
const series = ref([]);
const assetEvents = ref([]);
const loading = ref(false);
const error = ref("");
const dateRange = ref([]);
const filters = reactive({
  owner_id: route.query.owner_id ? Number(route.query.owner_id) : null,
  domain_id: route.query.domain_id ? Number(route.query.domain_id) : null,
});
if (route.query.start_date && route.query.end_date) dateRange.value = [route.query.start_date, route.query.end_date];

function sourceName(source) {
  return source?.type === "self" ? "本人记录" : [source?.name, source?.branch_name].filter(Boolean).join(" · ") || "体检机构";
}

function compact(value) {
  if (value === null || value === undefined) return "—";
  const number = Number(value);
  return Number.isInteger(number) ? number : Number(number.toFixed(2));
}

function changeLabel(value) {
  if (value === null || value === undefined) return "首次记录";
  const number = Number(value);
  if (Math.abs(number) < 0.005) return "基本持平";
  return `${number > 0 ? "上升" : "下降"} ${Math.abs(number).toFixed(2)}`;
}

function changeClass(value) {
  if (value === null || value === undefined || Math.abs(Number(value)) < 0.005) return "is-steady";
  return Number(value) > 0 ? "is-up" : "is-down";
}

function chartPoints(points) {
  if (!points?.length) return [];
  const values = points.map((point) => Number(point.value));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  return points.map((point, index) => ({
    ...point,
    x: points.length === 1 ? 180 : 16 + (index / (points.length - 1)) * 328,
    y: 122 - ((Number(point.value) - min) / range) * 96,
  }));
}

function sparkline(points) {
  return chartPoints(points).map((point) => `${point.x},${point.y}`).join(" ");
}

function formatShortDate(value) {
  if (!value) return "—";
  return new Date(`${value}T00:00:00`).toLocaleDateString("zh-CN", { month: "short", day: "numeric" });
}

function cleanParams(value) {
  const result = { ...value };
  Object.keys(result).forEach((key) => {
    if (result[key] === null || result[key] === undefined || result[key] === "") delete result[key];
  });
  return result;
}

async function load() {
  if (!filters.domain_id) return;
  loading.value = true;
  error.value = "";
  try {
    const params = cleanParams({
      owner_id: filters.owner_id,
      start_date: dateRange.value?.[0],
      end_date: dateRange.value?.[1],
    });
    const { data } = await fetchHealthTrends(filters.domain_id, params);
    series.value = data.series_by_indicator || [];
    assetEvents.value = data.asset_events || [];
  } catch (fetchError) {
    error.value = fetchError?.response?.data?.message || "健康趋势暂时没有加载成功，请稍后重试";
  } finally {
    loading.value = false;
  }
}

async function apply() {
  const query = cleanParams({
    ...filters,
    start_date: dateRange.value?.[0],
    end_date: dateRange.value?.[1],
  });
  await router.replace({ query });
  await load();
}

async function openAsset(event) {
  try {
    const params = filters.owner_id ? { owner_id: filters.owner_id } : {};
    const { data } = await fetchHealthAssetContent(event.health_data_id, event.asset.id, params);
    const url = URL.createObjectURL(data);
    window.open(url, "_blank", "noopener");
    window.setTimeout(() => URL.revokeObjectURL(url), 60000);
  } catch (assetError) {
    ElMessage.error(assetError?.response?.data?.message || "附件暂时无法打开");
  }
}

onMounted(async () => {
  const [domainResponse, friendResponse] = await Promise.all([fetchHealthDomains(), fetchFriends()]);
  domains.value = domainResponse.data.items || [];
  filters.domain_id ||= domains.value[0]?.id;
  owners.value = buildHealthOwnerOptions(friendResponse.data, auth.user).map((item) => ({
    ...item,
    value: item.value === "self" ? null : Number(item.value),
  }));
  await load();
});
</script>
