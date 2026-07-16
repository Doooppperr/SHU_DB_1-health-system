<template>
  <div class="workspace-page">
    <section class="page-intro">
      <div><p>先预约，再体检</p><h2>体检预约</h2><span>选择机构、已审核套餐和日期；同一用户同一天只能保留一条有效预约。</span></div>
    </section>

    <el-card shadow="never">
      <el-form label-position="top">
        <div class="responsive-form-grid">
          <el-form-item label="预约日期" required>
            <el-date-picker v-model="appointmentDate" type="date" value-format="YYYY-MM-DD" :disabled-date="disabledDate" style="width:100%" @change="loadAvailability" />
          </el-form-item>
          <el-form-item label="体检机构" required>
            <el-select v-model="institutionId" filterable style="width:100%" @change="packageId=null">
              <el-option v-for="entry in availability" :key="entry.institution.id" :label="`${entry.institution.name} · ${entry.institution.branch_name}`" :value="entry.institution.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="体检套餐" required>
            <el-select v-model="packageId" style="width:100%" :disabled="!selectedInstitution">
              <el-option v-for="item in selectedInstitution?.packages || []" :key="item.id" :label="`${item.name} · ¥${Number(item.price).toFixed(2)}`" :value="item.id" />
            </el-select>
          </el-form-item>
        </div>
        <el-alert v-if="selectedInstitution" :type="selectedInstitution.is_full ? 'warning' : 'success'" :closable="false" show-icon>
          <template #title>{{ quotaText }}</template>
        </el-alert>
        <div style="margin-top:18px;text-align:right">
          <el-tooltip :content="selectedInstitution?.is_full ? '今日已无预约名额' : ''" :disabled="!selectedInstitution?.is_full">
            <span><el-button type="primary" :disabled="!canSubmit" :loading="submitting" @click="submitBooking">发送预约</el-button></span>
          </el-tooltip>
        </div>
      </el-form>
    </el-card>

    <el-card shadow="never" class="table-card">
      <template #header><strong>我的预约</strong></template>
      <el-table :data="appointments" v-loading="loadingAppointments" empty-text="暂无预约记录">
        <el-table-column prop="appointment_date" label="预约日期" width="130" />
        <el-table-column label="机构" min-width="210"><template #default="scope">{{ scope.row.institution?.name }} · {{ scope.row.institution?.branch_name }}</template></el-table-column>
        <el-table-column prop="package_name" label="套餐" min-width="160" />
        <el-table-column label="状态" width="130"><template #default="scope"><el-tag :type="statusType(scope.row.status)">{{ statusLabel(scope.row.status) }}</el-tag></template></el-table-column>
        <el-table-column label="操作" width="160"><template #default="scope"><el-button v-if="scope.row.status==='unfulfilled'" link type="danger" @click="cancel(scope.row)">取消预约</el-button><router-link v-if="scope.row.report_id && scope.row.status==='fulfilled'" :to="{name:'report-detail',params:{id:scope.row.report_id}}">查看报告</router-link></template></el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { cancelAppointment, createAppointment, fetchAppointmentAvailability, fetchMyAppointments } from "../api/appointments";

function localDate(offset=0){const value=new Date();value.setDate(value.getDate()+offset);return `${value.getFullYear()}-${String(value.getMonth()+1).padStart(2,'0')}-${String(value.getDate()).padStart(2,'0')}`;}
const appointmentDate=ref(localDate()),institutionId=ref(null),packageId=ref(null),availability=ref([]),appointments=ref([]),submitting=ref(false),loadingAppointments=ref(false);
const selectedInstitution=computed(()=>availability.value.find((item)=>item.institution.id===institutionId.value));
const quotaText=computed(()=>{const item=selectedInstitution.value;if(!item)return "";if(item.daily_limit===null)return "该机构当前不限预约名额";if(item.is_full)return "今日已无预约名额";return `所选日期还剩 ${item.remaining} 个名额（每日上限 ${item.daily_limit}）`;});
const canSubmit=computed(()=>Boolean(appointmentDate.value&&institutionId.value&&packageId.value&&!selectedInstitution.value?.is_full));
const statusMap={unfulfilled:"未履约",awaiting_report:"待上传报告",fulfilled:"已履约",invalidated:"已失效",cancelled:"已取消"};
const statusLabel=(value)=>statusMap[value]||value;
const statusType=(value)=>({fulfilled:"success",invalidated:"danger",cancelled:"info",awaiting_report:"warning"}[value]||"");
function disabledDate(value){const start=new Date();start.setHours(0,0,0,0);const end=new Date(start);end.setDate(end.getDate()+30);return value<start||value>end;}
async function loadAvailability(){if(!appointmentDate.value)return;try{availability.value=(await fetchAppointmentAvailability(appointmentDate.value)).data.items||[];if(!availability.value.some((item)=>item.institution.id===institutionId.value)){institutionId.value=null;packageId.value=null;}}catch(error){ElMessage.error(error?.response?.data?.message||"预约名额加载失败");}}
async function loadAppointments(){loadingAppointments.value=true;try{appointments.value=(await fetchMyAppointments()).data.items||[];}finally{loadingAppointments.value=false;}}
async function submitBooking(){if(!canSubmit.value){if(selectedInstitution.value?.is_full)ElMessage.warning("今日已无预约名额");return;}submitting.value=true;try{await createAppointment({appointment_date:appointmentDate.value,institution_id:institutionId.value,package_id:packageId.value});ElMessage.success("预约成功，当前状态为未履约");await Promise.all([loadAvailability(),loadAppointments()]);}catch(error){ElMessage.error(error?.response?.data?.message||"预约失败");await loadAvailability();}finally{submitting.value=false;}}
async function cancel(item){try{await ElMessageBox.confirm("取消后该名额会立即释放，确认取消预约？","取消预约",{type:"warning"});await cancelAppointment(item.id);ElMessage.success("预约已取消");await Promise.all([loadAvailability(),loadAppointments()]);}catch(error){if(error!=="cancel"&&error!=="close")ElMessage.error(error?.response?.data?.message||"取消失败");}}
onMounted(()=>Promise.all([loadAvailability(),loadAppointments()]));
</script>
