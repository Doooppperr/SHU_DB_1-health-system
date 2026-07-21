<template>
  <div class="workspace-page user-platform-page">
    <section class="user-page-lead">
      <div>
        <span class="user-kicker">体检预约</span>
        <h2>为自己和家人安排一次体检</h2>
        <p>先选日期和机构，再确认套餐与受检者。同行人会作为一个预约一起提交，不会出现有人成功、有人失败。</p>
      </div>
    </section>

    <el-card shadow="never" class="user-panel booking-flow-card">
      <el-steps :active="step - 1" finish-status="success" align-center class="booking-steps">
        <el-step title="选择时间与机构" />
        <el-step title="选择体检套餐" />
        <el-step title="确认受检者" />
      </el-steps>

      <section v-if="step === 1" class="booking-step-panel">
        <div class="booking-step-heading"><span>第一步</span><h3>什么时候去，想去哪家机构？</h3><p>可预约未来 30 天，选择日期后会显示当天剩余名额。</p></div>
        <el-form label-position="top">
          <el-form-item label="体检日期" required>
            <el-date-picker v-model="form.appointment_date" type="date" value-format="YYYY-MM-DD" :disabled-date="disabledDate" style="width: 100%" @change="dateChanged" />
          </el-form-item>
          <div v-loading="availabilityLoading" class="booking-institution-grid">
            <button
              v-for="option in availability"
              :key="option.institution.id"
              type="button"
              class="booking-choice-card"
              :class="{ 'is-selected': form.institution_id === option.institution.id, 'is-disabled': option.remaining === 0 }"
              @click="selectInstitution(option)"
            >
              <span class="booking-choice-card__check">{{ form.institution_id === option.institution.id ? "✓" : "院" }}</span>
              <strong>{{ option.institution.name }}</strong>
              <small>{{ option.institution.branch_name }}</small>
              <p>{{ option.remaining == null ? "当天名额充足" : option.remaining ? `当天剩余 ${option.remaining} 个名额` : "当天已约满" }}</p>
            </button>
            <el-empty v-if="!availabilityLoading && !availability.length" description="当天暂时没有可预约机构" />
          </div>
        </el-form>
      </section>

      <section v-else-if="step === 2" class="booking-step-panel">
        <div class="booking-step-heading"><span>第二步</span><h3>选择适合这次需要的套餐</h3><p>{{ selectedInstitution?.institution?.name }} · {{ selectedInstitution?.institution?.branch_name }}</p></div>
        <div class="booking-package-grid">
          <button
            v-for="pkg in selectedInstitution?.packages || []"
            :key="pkg.id"
            type="button"
            class="booking-package-choice"
            :class="{ 'is-selected': form.package_id === pkg.id }"
            @click="form.package_id = pkg.id"
          >
            <div><el-tag effect="plain">{{ packageTypeLabel(pkg.package_type) }}</el-tag><strong>¥ {{ Number(pkg.price || 0).toFixed(0) }}</strong></div>
            <h4>{{ pkg.name }}</h4>
            <p>{{ pkg.audience || genderLabel(pkg.gender_scope) }}</p>
            <div class="journey-domain-list"><span v-for="domain in pkg.domains || []" :key="domain.id">{{ domain.name }}</span></div>
            <small>{{ pkg.focus_area }}</small>
          </button>
        </div>
      </section>

      <section v-else class="booking-step-panel">
        <div class="booking-step-heading"><span>第三步</span><h3>确认谁参加这次体检</h3><p>最多 5 人。只有已经授权你代预约的亲友才会出现在这里。</p></div>
        <el-form label-position="top">
          <el-form-item label="受检者" required>
            <el-select v-model="form.participant_user_ids" multiple :multiple-limit="5" style="width: 100%">
              <el-option v-for="person in participantOptions" :key="person.id" :label="person.label" :value="person.id" />
            </el-select>
          </el-form-item>
        </el-form>

        <div v-if="selectedPackage" class="booking-review-card">
          <div><span>预约日期</span><strong>{{ formatDate(form.appointment_date) }}</strong></div>
          <div><span>体检机构</span><strong>{{ selectedInstitution?.institution?.name }} · {{ selectedInstitution?.institution?.branch_name }}</strong></div>
          <div><span>体检套餐</span><strong>{{ selectedPackage.name }} · ¥ {{ Number(selectedPackage.price || 0).toFixed(0) }} / 人</strong></div>
          <div><span>受检人数</span><strong>{{ form.participant_user_ids.length }} 人</strong></div>
        </div>

        <el-alert v-if="selectedPackage" type="info" :closable="false" show-icon>
          <template #title>预约前请确认</template>
          <p>{{ selectedPackage.booking_notice || "具体检查安排和注意事项以机构现场说明为准。" }}</p>
        </el-alert>
        <el-checkbox v-model="form.notice_confirmed" class="booking-notice-check">我已阅读并确认上述预约与检查须知</el-checkbox>
        <el-alert v-if="selectedInstitution" :type="enough ? 'success' : 'warning'" :closable="false" :title="quotaText" show-icon />
      </section>

      <footer class="booking-flow-actions">
        <el-button v-if="step > 1" @click="step -= 1">上一步</el-button>
        <span></span>
        <el-button v-if="step < 3" type="primary" :disabled="!canContinue" @click="step += 1">继续</el-button>
        <template v-else>
          <el-button v-if="!enough" @click="joinWaitlist">到空位时提醒我</el-button>
          <el-button type="primary" :disabled="!canBook" :loading="submitting" @click="book">确认预约</el-button>
        </template>
      </footer>
    </el-card>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" :closable="false" show-icon />

    <section class="booking-management-grid">
      <el-card shadow="never" class="user-panel">
        <template #header><div class="user-section-heading"><div><span>我的安排</span><h3>预约记录</h3></div><small>{{ groups.length }} 组</small></div></template>
        <div class="booking-record-list">
          <article v-for="group in groups" :key="group.id" class="booking-record-card">
            <div class="booking-record-card__date"><strong>{{ dayOfMonth(group.appointment_date) }}</strong><span>{{ monthLabel(group.appointment_date) }}</span></div>
            <div class="booking-record-card__body">
              <div><el-tag v-for="status in group.status_codes || []" :key="status" :type="appointmentMeta(status).type" effect="light">{{ appointmentMeta(status).label }}</el-tag></div>
              <h4>{{ group.package?.name || group.package_name_snapshot }}</h4>
              <p>{{ group.institution?.name }} · {{ group.institution?.branch_name }}</p>
              <small>{{ (group.participant_names || []).join("、") }} · 共 {{ group.party_size }} 人</small>
            </div>
            <el-button v-if="group.can_cancel" link type="danger" @click="cancelGroup(group)">取消整组</el-button>
          </article>
          <el-empty v-if="!groups.length" description="还没有预约记录" :image-size="80" />
        </div>
      </el-card>

      <el-card shadow="never" class="user-panel">
        <template #header><div class="user-section-heading"><div><span>空位动态</span><h3>我的提醒</h3></div><small>{{ activeWaitlistCount }} 条生效中</small></div></template>
        <div class="waitlist-card-list">
          <article v-for="item in waitlists" :key="item.id" class="waitlist-card">
            <div><el-tag :type="item.status === 'active' ? 'warning' : 'info'" effect="light">{{ item.status_label || WAITLIST_STATUS[item.status] || "状态更新中" }}</el-tag><h4>{{ item.package?.name }}</h4><p>{{ item.institution?.name }} · {{ formatDate(item.appointment_date) }}</p></div>
            <el-button v-if="item.status === 'active'" link type="danger" @click="cancelWaitlist(item)">取消提醒</el-button>
          </article>
          <el-empty v-if="!waitlists.length" description="没有空位提醒" :image-size="80" />
        </div>
      </el-card>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { useRoute } from "vue-router";
import {
  cancelBookingGroup,
  cancelWaitlistSubscription,
  createBookingGroup,
  createWaitlistSubscription,
  fetchAppointmentAvailability,
  fetchBookingGroups,
  fetchWaitlistSubscriptions,
} from "../api/appointments";
import { fetchFriends } from "../api/friends";
import { useAuthStore } from "../stores/auth";
import {
  WAITLIST_STATUS,
  appointmentMeta,
  formatDate,
  genderLabel,
  packageTypeLabel,
} from "../utils/userPlatform";

const route = useRoute();
const auth = useAuthStore();
const step = ref(1);
const availability = ref([]);
const groups = ref([]);
const waitlists = ref([]);
const relations = ref([]);
const submitting = ref(false);
const availabilityLoading = ref(false);
const errorMessage = ref("");

function localDate() {
  const date = new Date();
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

const form = reactive({
  appointment_date: route.query.date || localDate(),
  institution_id: route.query.institution_id ? Number(route.query.institution_id) : null,
  package_id: route.query.package_id ? Number(route.query.package_id) : null,
  participant_user_ids: [],
  notice_confirmed: false,
});
const selectedInstitution = computed(() => availability.value.find((item) => item.institution.id === form.institution_id));
const selectedPackage = computed(() => selectedInstitution.value?.packages.find((item) => item.id === form.package_id));
const participantOptions = computed(() => [
  { id: auth.user.id, label: `我本人（${auth.user.real_name || auth.user.username}）` },
  ...relations.value.filter((item) => item.booking_auth_status).map((item) => ({
    id: item.friend_user.id,
    label: `${item.friend_user.real_name || item.friend_user.username}（已授权代预约）`,
  })),
]);
const remaining = computed(() => selectedInstitution.value?.remaining);
const enough = computed(() => remaining.value == null || remaining.value >= form.participant_user_ids.length);
const quotaText = computed(() => {
  if (remaining.value == null) return "当天名额充足，可以提交预约";
  if (enough.value) return `当天还剩 ${remaining.value} 个名额，可以容纳当前 ${form.participant_user_ids.length} 人`;
  return `当天只剩 ${remaining.value} 个名额，暂时无法容纳当前 ${form.participant_user_ids.length} 人`;
});
const canContinue = computed(() => step.value === 1
  ? Boolean(form.appointment_date && form.institution_id)
  : Boolean(form.package_id));
const canBook = computed(() => Boolean(
  form.appointment_date
  && form.institution_id
  && form.package_id
  && form.participant_user_ids.length
  && form.notice_confirmed
  && enough.value
));
const activeWaitlistCount = computed(() => waitlists.value.filter((item) => item.status === "active").length);

function disabledDate(value) {
  const start = new Date();
  start.setHours(0, 0, 0, 0);
  const end = new Date(start);
  end.setDate(end.getDate() + 30);
  return value < start || value > end;
}

function dayOfMonth(value) {
  return new Date(`${value}T00:00:00`).getDate();
}

function monthLabel(value) {
  return new Date(`${value}T00:00:00`).toLocaleDateString("zh-CN", { month: "short" });
}

function selectInstitution(option) {
  form.institution_id = option.institution.id;
  if (!option.packages?.some((item) => item.id === form.package_id)) form.package_id = null;
}

async function dateChanged() {
  form.institution_id = null;
  form.package_id = null;
  await loadAvailability();
}

async function loadAvailability() {
  availabilityLoading.value = true;
  try {
    availability.value = (await fetchAppointmentAvailability(form.appointment_date)).data.items || [];
    if (form.institution_id && !selectedInstitution.value) {
      form.institution_id = null;
      form.package_id = null;
    }
  } finally {
    availabilityLoading.value = false;
  }
}

async function reload() {
  const [groupResponse, waitlistResponse] = await Promise.all([fetchBookingGroups(), fetchWaitlistSubscriptions()]);
  groups.value = groupResponse.data.items || [];
  waitlists.value = waitlistResponse.data.items || [];
}

function payload() {
  return { ...form, participant_user_ids: [...form.participant_user_ids] };
}

async function book() {
  submitting.value = true;
  try {
    await createBookingGroup(payload());
    ElMessage.success("预约成功，所有受检者都已加入本次安排");
    step.value = 1;
    form.notice_confirmed = false;
    await Promise.all([loadAvailability(), reload()]);
  } catch (error) {
    const data = error?.response?.data || {};
    if (data.code === "APPOINTMENT_DATE_CONFLICT") {
      const names = (data.conflicts || []).map((item) => item.display_name).filter(Boolean);
      const detail = names.length ? `受检者：${names.join("、")}。` : "";
      await ElMessageBox.alert(
        `${detail}${data.message || "当天已有预约，请先查看原预约后再选择其他日期"}`,
        "当天已有预约",
        { type: "warning", confirmButtonText: "我知道了" },
      );
    } else {
      ElMessage.error(data.message || "预约没有提交成功，请稍后重试");
    }
    await loadAvailability();
  } finally {
    submitting.value = false;
  }
}

async function joinWaitlist() {
  try {
    await createWaitlistSubscription(payload());
    ElMessage.success("空位提醒已开启；收到提醒后仍需回来确认预约");
    await reload();
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || "空位提醒开启失败");
  }
}

async function cancelGroup(group) {
  try {
    await ElMessageBox.confirm(
      "这会取消组内所有尚未到检的预约，确认继续吗？",
      "取消整组预约",
      { type: "warning", confirmButtonText: "确认取消", cancelButtonText: "保留预约" }
    );
    await cancelBookingGroup(group.id);
    ElMessage.success("整组预约已取消");
    await Promise.all([loadAvailability(), reload()]);
  } catch (error) {
    if (error !== "cancel" && error !== "close") ElMessage.error(error?.response?.data?.message || "取消失败");
  }
}

async function cancelWaitlist(item) {
  try {
    await cancelWaitlistSubscription(item.id);
    ElMessage.success("空位提醒已取消");
    await reload();
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || "取消提醒失败");
  }
}

onMounted(async () => {
  try {
    const friendResponse = await fetchFriends();
    relations.value = friendResponse.data.outgoing || [];
    form.participant_user_ids = [auth.user.id];
    await Promise.all([loadAvailability(), reload()]);
    if (form.institution_id && selectedInstitution.value) step.value = form.package_id ? 3 : 2;
  } catch (error) {
    errorMessage.value = error?.response?.data?.message || "预约信息暂时没有加载成功，请稍后重试";
  }
});
</script>
