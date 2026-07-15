<template>
  <div class="workspace-page">
    <section class="page-intro">
      <div>
        <p>体检安排</p>
        <h2>登记体检</h2>
        <span>直接选择机构、可选套餐和体检日期，不需要先进入机构详情。</span>
      </div>
    </section>

    <el-card shadow="never" class="form-card registration-card">
      <template #header>
        <div class="card-heading">
          <div>
            <h3>新增体检登记</h3>
            <p>机构提交报告后，系统会按姓名、健康身份码、日期和机构自动匹配。</p>
          </div>
        </div>
      </template>

      <el-alert
        title="机构未匹配的体检数据只保留 60 天，超过期限后无法匹配。"
        type="warning"
        show-icon
        :closable="false"
      />

      <el-form
        :model="form"
        label-position="top"
        class="registration-form"
        @submit.prevent="submitRegistration"
      >
        <div class="registration-form-grid">
          <el-form-item label="体检机构" required>
            <el-select
              v-model="form.institution_id"
              placeholder="请选择体检机构"
              filterable
              style="width: 100%"
              @change="handleInstitutionChange"
            >
              <el-option
                v-for="item in institutions"
                :key="item.id"
                :label="`${item.name} · ${item.branch_name}`"
                :value="item.id"
              />
            </el-select>
          </el-form-item>

          <el-form-item label="体检套餐（可选）">
            <el-select
              v-model="form.package_id"
              placeholder="暂不选择套餐"
              clearable
              filterable
              :disabled="!form.institution_id"
              :loading="packagesLoading"
              style="width: 100%"
            >
              <el-option
                v-for="item in packages"
                :key="item.id"
                :label="`${item.name} · ¥${item.price}`"
                :value="item.id"
              />
            </el-select>
          </el-form-item>

          <el-form-item label="体检日期" required>
            <el-date-picker
              v-model="form.exam_date"
              type="date"
              value-format="YYYY-MM-DD"
              placeholder="请选择体检日期"
              style="width: 100%"
            />
          </el-form-item>
        </div>

        <div class="registration-form-actions">
          <el-button
            type="primary"
            native-type="submit"
            :loading="saving"
            :disabled="loading"
          >
            确认登记
          </el-button>
        </div>
      </el-form>
    </el-card>

    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="card-heading">
          <div>
            <h3>我的体检登记</h3>
            <p>查看等待机构提交、已匹配和已取消的登记。</p>
          </div>
          <el-button link type="primary" :loading="loading" @click="loadRegistrations">刷新</el-button>
        </div>
      </template>

      <el-table :data="registrations" v-loading="loading" empty-text="暂无体检登记">
        <el-table-column label="体检日期" prop="exam_date" min-width="130" />
        <el-table-column label="体检机构" min-width="240">
          <template #default="scope">
            <strong>{{ scope.row.institution?.name || "-" }}</strong>
            <span class="registration-branch">{{ scope.row.institution?.branch_name || "" }}</span>
          </template>
        </el-table-column>
        <el-table-column label="套餐" min-width="180">
          <template #default="scope">{{ scope.row.package?.name || "暂未选择" }}</template>
        </el-table-column>
        <el-table-column label="状态" width="130">
          <template #default="scope">
            <el-tag :type="statusType(scope.row.status)">{{ scope.row.display_status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="110" fixed="right">
          <template #default="scope">
            <el-button
              v-if="scope.row.status === 'awaiting_report'"
              link
              type="danger"
              @click="cancel(scope.row)"
            >
              取消登记
            </el-button>
            <span v-else>-</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { useRoute } from "vue-router";

import {
  cancelRegistration,
  createRegistration,
  fetchRegistrations,
} from "../api/health";
import {
  fetchInstitutionPackages,
  fetchInstitutions,
} from "../api/institutions";

const route = useRoute();
const institutions = ref([]);
const packages = ref([]);
const registrations = ref([]);
const loading = ref(false);
const packagesLoading = ref(false);
const saving = ref(false);
const now = new Date();
const localToday = [
  now.getFullYear(),
  String(now.getMonth() + 1).padStart(2, "0"),
  String(now.getDate()).padStart(2, "0"),
].join("-");
const form = reactive({
  institution_id: null,
  package_id: null,
  exam_date: localToday,
});

function statusType(status) {
  if (status === "matched") return "success";
  if (status === "cancelled") return "info";
  return "warning";
}

async function loadPackages(institutionId) {
  packages.value = [];
  if (!institutionId) return;
  packagesLoading.value = true;
  try {
    const { data } = await fetchInstitutionPackages(institutionId);
    packages.value = data.items || [];
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || "体检套餐加载失败");
  } finally {
    packagesLoading.value = false;
  }
}

async function handleInstitutionChange(institutionId) {
  form.package_id = null;
  await loadPackages(institutionId);
}

async function loadRegistrations() {
  loading.value = true;
  try {
    const { data } = await fetchRegistrations();
    registrations.value = data.items || [];
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || "体检登记加载失败");
  } finally {
    loading.value = false;
  }
}

async function submitRegistration() {
  if (!form.institution_id) {
    ElMessage.error("请选择体检机构");
    return;
  }
  if (!form.exam_date) {
    ElMessage.error("请选择体检日期");
    return;
  }

  saving.value = true;
  try {
    const { data } = await createRegistration({
      institution_id: form.institution_id,
      package_id: form.package_id || null,
      exam_date: form.exam_date,
    });
    ElMessage.success(
      data.match_result === "matched"
        ? "登记成功，已自动匹配机构报告"
        : "登记成功，等待机构提交报告"
    );
    await loadRegistrations();
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || "体检登记失败");
  } finally {
    saving.value = false;
  }
}

async function cancel(row) {
  try {
    await ElMessageBox.confirm(
      `确认取消 ${row.exam_date} 的体检登记？`,
      "取消登记",
      { type: "warning", confirmButtonText: "确认取消", cancelButtonText: "保留登记" }
    );
    await cancelRegistration(row.id);
    ElMessage.success("体检登记已取消");
    await loadRegistrations();
  } catch (error) {
    if (error !== "cancel" && error !== "close") {
      ElMessage.error(error?.response?.data?.message || "取消登记失败");
    }
  }
}

onMounted(async () => {
  loading.value = true;
  try {
    const [institutionResponse, registrationResponse] = await Promise.all([
      fetchInstitutions(),
      fetchRegistrations(),
    ]);
    institutions.value = institutionResponse.data.items || [];
    registrations.value = registrationResponse.data.items || [];

    const requestedInstitutionId = Number(route.query.institution_id);
    if (
      Number.isInteger(requestedInstitutionId)
      && institutions.value.some((item) => item.id === requestedInstitutionId)
    ) {
      form.institution_id = requestedInstitutionId;
      await loadPackages(requestedInstitutionId);
    }
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || "体检登记页面加载失败");
  } finally {
    loading.value = false;
  }
});
</script>

<style scoped>
.registration-card {
  width: 100%;
}

.registration-form {
  margin-top: 20px;
}

.registration-form-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.registration-form-actions {
  display: flex;
  justify-content: flex-end;
}

.registration-form-actions .el-button {
  min-width: 128px;
}

.registration-branch {
  display: block;
  margin-top: 4px;
  color: var(--color-text-secondary);
  font-size: var(--text-xs);
}

@media (max-width: 980px) {
  .registration-form-grid {
    grid-template-columns: 1fr;
    gap: 0;
  }

  .registration-form-actions .el-button {
    width: 100%;
  }
}
</style>
