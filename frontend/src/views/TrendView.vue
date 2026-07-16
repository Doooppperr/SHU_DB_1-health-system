<template>
  <div class="workspace-page">
    <section class="page-intro">
      <div>
        <p>每日有效指标</p>
        <h2>指标趋势</h2>
        <span>同日同指标优先采用机构报告；否则采用当天最后一次自测。</span>
      </div>
    </section>

    <el-card shadow="never">
      <div class="filter-row">
        <label class="filter-field">
          <span class="filter-field-label">成员</span>
          <el-select
            v-model="ownerValue"
            :loading="ownersLoading"
            placeholder="请选择本人或已授权亲友"
          >
            <el-option
              v-for="option in ownerOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </label>
        <label class="filter-field">
          <span class="filter-field-label">指标</span>
          <el-select v-model="indicatorId" filterable placeholder="请选择指标">
            <el-option
              v-for="indicator in indicators"
              :key="indicator.id"
              :label="`${indicator.name}（${indicator.unit || '-'}）`"
              :value="indicator.id"
            />
          </el-select>
        </label>
        <el-button type="primary" :loading="loading" @click="loadTrend">查询</el-button>
      </div>
    </el-card>

    <el-alert
      v-if="errorMessage"
      :title="errorMessage"
      type="error"
      :closable="false"
      show-icon
    />

    <section class="metric-grid">
      <article v-for="metric in metrics" :key="metric.label" class="metric-card">
        <div>
          <small>{{ metric.label }}</small>
          <strong>{{ metric.value }}</strong>
          <p>{{ unit }}</p>
        </div>
      </article>
    </section>

    <el-card shadow="never" v-loading="loading">
      <template #header>
        <strong>{{ selectedOwnerLabel }} · {{ currentIndicator?.name || "指标" }}</strong>
      </template>
      <div ref="chartEl" style="height: 420px" />
      <el-table :data="points" empty-text="暂无趋势数据">
        <el-table-column prop="date" label="日期" />
        <el-table-column label="有效值">
          <template #default="scope">{{ scope.row.value }} {{ unit }}</template>
        </el-table-column>
        <el-table-column label="来源">
          <template #default="scope">
            <el-tag :type="scope.row.source === 'institution_report' ? 'success' : 'info'">
              {{ scope.row.source === "institution_report" ? "机构报告" : "用户自测" }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";

import { fetchFriends } from "../api/friends";
import { fetchTrend } from "../api/health";
import { fetchIndicatorDicts } from "../api/indicators";
import { useAuthStore } from "../stores/auth";
import { initTrendChart } from "../utils/echartsRuntime";
import {
  SELF_OWNER_VALUE,
  buildHealthOwnerOptions,
  ownerRequestParams,
} from "../utils/healthOwners";

const authStore = useAuthStore();
const indicators = ref([]);
const ownerValue = ref(SELF_OWNER_VALUE);
const ownerOptions = ref(buildHealthOwnerOptions({}, authStore.user));
const indicatorId = ref(null);
const points = ref([]);
const summary = ref({});
const loading = ref(false);
const ownersLoading = ref(false);
const errorMessage = ref("");
const chartEl = ref(null);
let chart;

const selectedOwnerLabel = computed(
  () =>
    ownerOptions.value.find((option) => option.value === ownerValue.value)?.label ||
    "我本人"
);
const currentIndicator = computed(() =>
  indicators.value.find((indicator) => indicator.id === indicatorId.value)
);
const unit = computed(() => currentIndicator.value?.unit || "");
const metrics = computed(() => [
  { label: "最新值", value: summary.value.latest ?? "-" },
  { label: "最高值", value: summary.value.highest ?? "-" },
  { label: "最低值", value: summary.value.lowest ?? "-" },
  { label: "有效记录", value: summary.value.count ?? 0 },
]);

const render = () => {
  if (!chartEl.value) return;
  chart ||= initTrendChart(chartEl.value);
  chart.setOption(
    {
      tooltip: { trigger: "axis" },
      grid: { left: 50, right: 28, top: 30, bottom: 45 },
      xAxis: { type: "category", data: points.value.map((point) => point.date) },
      yAxis: { type: "value", name: unit.value },
      series: [
        {
          type: "line",
          smooth: true,
          data: points.value.map((point) => ({
            value: point.value,
            itemStyle: {
              color: point.source === "institution_report" ? "#2f855a" : "#3b82f6",
            },
          })),
          symbolSize: 9,
        },
      ],
    },
    true
  );
};

const loadOwners = async () => {
  ownersLoading.value = true;
  try {
    const { data } = await fetchFriends();
    ownerOptions.value = buildHealthOwnerOptions(data, authStore.user);
    if (!ownerOptions.value.some((option) => option.value === ownerValue.value)) {
      ownerValue.value = SELF_OWNER_VALUE;
    }
  } finally {
    ownersLoading.value = false;
  }
};

const loadTrend = async () => {
  if (!indicatorId.value) return;
  loading.value = true;
  errorMessage.value = "";
  try {
    const { data } = await fetchTrend(
      indicatorId.value,
      ownerRequestParams(ownerValue.value)
    );
    points.value = data.points || [];
    summary.value = data.summary || {};
    await nextTick();
    render();
  } catch (error) {
    points.value = [];
    summary.value = {};
    if (error?.response?.status === 403) {
      errorMessage.value = "该亲友的授权已失效，已切换回本人数据。";
      await loadOwners();
      ownerValue.value = SELF_OWNER_VALUE;
    } else {
      errorMessage.value = error?.response?.data?.message || "指标趋势加载失败";
    }
  } finally {
    loading.value = false;
  }
};

const resizeChart = () => chart?.resize();

watch([ownerValue, indicatorId], loadTrend);

onMounted(async () => {
  const [indicatorResult, friendResult] = await Promise.allSettled([
    fetchIndicatorDicts(),
    loadOwners(),
  ]);
  if (indicatorResult.status === "fulfilled") {
    indicators.value = indicatorResult.value.data.items || [];
    indicatorId.value =
      indicators.value.find((indicator) => indicator.allow_self_measurement)?.id ||
      indicators.value[0]?.id ||
      null;
  } else {
    errorMessage.value = "指标字典加载失败";
  }
  if (friendResult.status === "rejected") {
    errorMessage.value = "亲友授权列表加载失败";
  }
  window.addEventListener("resize", resizeChart);
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", resizeChart);
  chart?.dispose();
});
</script>
