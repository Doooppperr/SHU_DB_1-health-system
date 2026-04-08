<template>
  <div class="home-shell">
    <el-card class="home-card">
      <template #header>
        <div class="top-bar">
          <span>指标趋势分析</span>
          <MainNavActions />
        </div>
      </template>

      <el-alert
        v-if="errorMessage"
        :title="errorMessage"
        type="error"
        :closable="false"
        style="margin-bottom: 16px"
      />

      <el-card shadow="never" style="margin-bottom: 16px">
        <div class="trend-filter-grid">
          <el-select v-model="selectedOwnerId" placeholder="选择档案归属人" style="width: 100%">
            <el-option v-for="owner in ownerOptions" :key="owner.id" :label="owner.label" :value="owner.id" />
          </el-select>

          <el-select v-model="selectedIndicatorId" filterable placeholder="选择指标" style="width: 100%">
            <el-option
              v-for="item in indicatorOptions"
              :key="item.id"
              :label="`${item.code} - ${item.name}`"
              :value="item.id"
            />
          </el-select>

          <el-button type="primary" :loading="loading" @click="loadTrend">查询趋势</el-button>
        </div>
      </el-card>

      <el-card shadow="never" v-if="trendResult">
        <template #header>
          <div class="top-bar">
            <span>
              {{ trendResult.owner.username }} · {{ trendResult.indicator.code }} - {{ trendResult.indicator.name }}
            </span>
            <el-tag>{{ trendResult.summary.count }} 条记录</el-tag>
          </div>
        </template>

        <div v-if="trendResult.indicator.value_type !== 'numeric'" class="trend-tip">
          当前指标为文本型，无法绘制数值折线图，仅展示历史明细。
        </div>

        <div v-else ref="chartRef" class="trend-chart"></div>

        <el-descriptions :column="4" border size="small" style="margin-bottom: 16px">
          <el-descriptions-item label="最新值">{{ trendResult.summary.latest ?? "-" }}</el-descriptions-item>
          <el-descriptions-item label="最小值">{{ trendResult.summary.min ?? "-" }}</el-descriptions-item>
          <el-descriptions-item label="最大值">{{ trendResult.summary.max ?? "-" }}</el-descriptions-item>
          <el-descriptions-item label="参考范围">
            {{ trendResult.summary.reference_low ?? "-" }} ~ {{ trendResult.summary.reference_high ?? "-" }}
          </el-descriptions-item>
        </el-descriptions>

        <el-table :data="trendResult.series" border empty-text="暂无趋势数据">
          <el-table-column prop="exam_date" label="体检日期" width="130" />
          <el-table-column prop="value" label="指标值" min-width="120" />
          <el-table-column label="是否异常" width="110">
            <template #default="scope">
              <el-tag :type="scope.row.is_abnormal ? 'danger' : 'success'">
                {{ scope.row.is_abnormal ? "异常" : "正常" }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="source" label="来源" width="90" />
          <el-table-column prop="record_id" label="档案ID" width="90" />
        </el-table>
      </el-card>
    </el-card>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import * as echarts from "echarts";

import MainNavActions from "../components/MainNavActions.vue";
import { fetchFriends } from "../api/friends";
import { fetchIndicatorDicts } from "../api/indicators";
import { fetchIndicatorTrend } from "../api/trends";
import { useAuthStore } from "../stores/auth";

const router = useRouter();
const authStore = useAuthStore();

const loading = ref(false);
const errorMessage = ref("");
const trendResult = ref(null);

const indicatorOptions = ref([]);
const manageableFriends = ref([]);

const selectedOwnerId = ref(null);
const selectedIndicatorId = ref(null);

const chartRef = ref(null);
let chartInstance = null;

const ownerOptions = computed(() => {
  const selfOption = authStore.user
    ? [{ id: authStore.user.id, label: `${authStore.user.username}（本人）` }]
    : [];
  const friendOptions = manageableFriends.value
    .filter((item) => item.friend_user?.id)
    .map((item) => ({
      id: item.friend_user.id,
      label: `${item.friend_user.username}（亲友）`,
    }));
  return [...selfOption, ...friendOptions];
});

const renderChart = async () => {
  if (!trendResult.value || trendResult.value.indicator.value_type !== "numeric") {
    return;
  }

  await nextTick();
  if (!chartRef.value) {
    return;
  }

  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value);
  }

  const xAxisData = trendResult.value.series.map((item) => item.exam_date);
  const yAxisData = trendResult.value.series.map((item) => item.numeric_value);

  const referenceLines = [];
  if (trendResult.value.summary.reference_low !== null) {
    referenceLines.push({
      yAxis: trendResult.value.summary.reference_low,
      name: "参考下限",
      lineStyle: { type: "dashed" },
    });
  }
  if (trendResult.value.summary.reference_high !== null) {
    referenceLines.push({
      yAxis: trendResult.value.summary.reference_high,
      name: "参考上限",
      lineStyle: { type: "dashed" },
    });
  }

  chartInstance.setOption({
    tooltip: { trigger: "axis" },
    grid: { left: 40, right: 24, top: 36, bottom: 36 },
    xAxis: {
      type: "category",
      data: xAxisData,
      boundaryGap: false,
    },
    yAxis: {
      type: "value",
      name: trendResult.value.indicator.unit || "",
      nameLocation: "end",
      nameTextStyle: { padding: [0, 0, 0, 8] },
    },
    series: [
      {
        type: "line",
        smooth: true,
        data: yAxisData,
        connectNulls: false,
        itemStyle: { color: "#2f7ed8" },
        lineStyle: { width: 3 },
        markLine: referenceLines.length ? { symbol: "none", data: referenceLines } : undefined,
      },
    ],
  });
};

const resizeChart = () => {
  if (chartInstance) {
    chartInstance.resize();
  }
};

const loadBaseData = async () => {
  if (!authStore.user) {
    await authStore.fetchMe();
  }

  const [friendsRes, indicatorsRes] = await Promise.all([fetchFriends(), fetchIndicatorDicts()]);
  manageableFriends.value = friendsRes.data.manageable || [];
  indicatorOptions.value = indicatorsRes.data.items || [];

  if (!selectedOwnerId.value && authStore.user) {
    selectedOwnerId.value = authStore.user.id;
  }
  if (!selectedIndicatorId.value && indicatorOptions.value.length) {
    selectedIndicatorId.value = indicatorOptions.value[0].id;
  }
};

const loadTrend = async () => {
  if (!selectedOwnerId.value || !selectedIndicatorId.value) {
    errorMessage.value = "请先选择归属人和指标";
    return;
  }

  loading.value = true;
  errorMessage.value = "";

  try {
    const { data } = await fetchIndicatorTrend(selectedIndicatorId.value, selectedOwnerId.value);
    trendResult.value = data;
    await renderChart();
  } catch (error) {
    trendResult.value = null;
    errorMessage.value = error?.response?.data?.message || "趋势数据加载失败";
  } finally {
    loading.value = false;
  }
};

const goInstitutions = () => {
  router.push({ name: "institutions" });
};

const goRecords = () => {
  router.push({ name: "records" });
};

const goFriends = () => {
  router.push({ name: "friends" });
};

const goProfile = () => {
  router.push({ name: "profile" });
};

const logout = () => {
  authStore.logout();
  router.push({ name: "login" });
};

onMounted(async () => {
  try {
    await loadBaseData();
    await loadTrend();
    window.addEventListener("resize", resizeChart);
  } catch (error) {
    errorMessage.value = error?.response?.data?.message || "趋势页面初始化失败";
  }
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", resizeChart);
  if (chartInstance) {
    chartInstance.dispose();
    chartInstance = null;
  }
});
</script>
