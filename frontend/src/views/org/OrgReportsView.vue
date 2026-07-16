<template>
  <div class="workspace-page">
    <section class="page-intro"><div><p>预约、到检与报告归档</p><h2>体检管理</h2><span>预约先处于未履约；确认到检后进入待上传报告，报告提交归档后才成为已履约。</span></div></section>

    <el-card shadow="never">
      <template #header><strong>每日预约上限</strong></template>
      <div class="filter-row">
        <el-switch v-model="limited" active-text="限制每日名额" inactive-text="不限名额" />
        <el-input-number v-if="limited" v-model="dailyLimit" :min="1" :step="1" />
        <el-button type="primary" :loading="capacitySaving" @click="saveCapacity">保存设置</el-button>
      </div>
      <p class="muted-copy">降低上限不会取消既有预约；已超出新上限的日期停止新增，直到余量重新大于 0。</p>
    </el-card>

    <el-card shadow="never" class="table-card">
      <div class="filter-row"><el-select v-model="status" @change="load"><el-option label="全部预约" value=""/><el-option v-for="item in appointmentStatuses" :key="item.value" :label="item.label" :value="item.value"/></el-select></div>
      <el-table :data="items" v-loading="loading" empty-text="暂无预约记录">
        <el-table-column prop="appointment_date" label="预约日期" width="125"/>
        <el-table-column label="用户" min-width="160"><template #default="s"><div class="table-primary"><strong>{{s.row.user?.name}}</strong><small>{{s.row.user?.health_id}}</small></div></template></el-table-column>
        <el-table-column prop="package_name" label="套餐" min-width="160"/>
        <el-table-column label="预约状态" width="130"><template #default="s"><el-tag :type="appointmentType(s.row.status)">{{appointmentLabel(s.row.status)}}</el-tag></template></el-table-column>
        <el-table-column label="报告" width="110"><template #default="s">{{reportLabel(s.row.report_status)}}</template></el-table-column>
        <el-table-column label="操作" min-width="310"><template #default="s">
          <template v-if="s.row.status==='unfulfilled'"><el-button link type="success" @click="attend(s.row)">确认到检</el-button><el-button link type="danger" @click="invalidate(s.row)">标记已失效</el-button></template>
          <template v-if="s.row.status==='awaiting_report'&&!s.row.report_id"><el-button link type="primary" @click="createManual(s.row)">手工录入报告</el-button><el-button link @click="openOcr(s.row)">OCR 上传</el-button></template>
          <template v-if="s.row.report_id"><el-button link @click="openDetailById(s.row.report_id)">查看报告</el-button><el-button v-if="s.row.report_status==='draft'" link type="success" @click="lockReport(s.row.report_id)">确认锁定</el-button><el-button v-if="s.row.report_status==='locked'" link type="primary" @click="submitReport(s.row.report_id)">提交归档</el-button></template>
        </template></el-table-column>
      </el-table>
    </el-card>

    <el-card shadow="never" class="table-card">
      <template #header><strong>历史归档报告</strong></template>
      <el-table :data="archivedReports" empty-text="暂无归档报告"><el-table-column prop="display_id" label="编号" width="110"/><el-table-column prop="subject_name_snapshot" label="受检者" min-width="140"/><el-table-column prop="exam_date" label="体检日期" width="125"/><el-table-column label="来源" min-width="160"><template #default="s">{{s.row.appointment_id?'预约履约':'历史归档'}}</template></el-table-column><el-table-column prop="indicator_count" label="指标数" width="90"/><el-table-column label="操作" width="100"><template #default="s"><el-button link @click="openDetailById(s.row.id)">查看</el-button></template></el-table-column></el-table>
    </el-card>

    <el-dialog v-model="ocrVisible" title="上传预约体检报告" width="560px"><el-alert title="OCR 仅创建待复核草稿；原文件会在确认锁定后删除。" type="warning" show-icon :closable="false"/><input style="margin:18px 0" type="file" accept=".pdf,.png,.jpg,.jpeg,.webp" @change="ocrFile=$event.target.files?.[0]||null"/><template #footer><el-button @click="ocrVisible=false">取消</el-button><el-button type="primary" :loading="ocrLoading" @click="runOcr">解析并创建草稿</el-button></template></el-dialog>

    <el-drawer v-model="detailVisible" title="报告详情" size="min(850px,96vw)"><template v-if="current"><el-descriptions :column="2" border><el-descriptions-item label="姓名">{{current.subject_name_snapshot}}</el-descriptions-item><el-descriptions-item label="健康身份码">{{current.subject_health_id}}</el-descriptions-item><el-descriptions-item label="体检日期">{{current.exam_date}}</el-descriptions-item><el-descriptions-item label="报告状态">{{reportLabel(current.status)}}</el-descriptions-item></el-descriptions><el-form v-if="current.status==='draft'" inline style="margin-top:18px"><el-form-item label="标准指标"><el-select v-model="indicatorForm.indicator_dict_id" filterable><el-option v-for="item in indicators" :key="item.id" :label="`${item.name}（${item.unit||'-'}）`" :value="item.id"/></el-select></el-form-item><el-form-item label="值"><el-input v-model="indicatorForm.value"/></el-form-item><el-button type="primary" @click="addIndicator">添加</el-button></el-form><el-table :data="current.indicators||[]"><el-table-column label="指标"><template #default="s">{{s.row.indicator?.name}}</template></el-table-column><el-table-column prop="value" label="值"/><el-table-column label="单位"><template #default="s">{{s.row.indicator?.unit}}</template></el-table-column><el-table-column v-if="current.status==='draft'" width="80"><template #default="s"><el-button link type="danger" @click="removeIndicator(s.row)">删除</el-button></template></el-table-column></el-table></template></el-drawer>
  </div>
</template>

<script setup>
import{onMounted,reactive,ref}from"vue";import{ElMessage,ElMessageBox}from"element-plus";import{fetchIndicatorDicts}from"../../api/indicators";import{addOrgReportIndicator,attendOrgAppointment,createOrgReport,deleteOrgReportIndicator,fetchOrgAppointmentCapacity,fetchOrgAppointments,fetchOrgReport,fetchOrgReports,invalidateOrgAppointment,lockOrgReport,submitOrgReport,updateOrgAppointmentCapacity,uploadOrgReportOcr}from"../../api/org";
const appointmentStatuses=[{value:"unfulfilled",label:"未履约"},{value:"awaiting_report",label:"待上传报告"},{value:"fulfilled",label:"已履约"},{value:"invalidated",label:"已失效"},{value:"cancelled",label:"已取消"}];const appointmentLabel=(v)=>appointmentStatuses.find((i)=>i.value===v)?.label||v;const appointmentType=(v)=>({fulfilled:"success",invalidated:"danger",cancelled:"info",awaiting_report:"warning"}[v]||"");const reportLabel=(v)=>({draft:"草稿",locked:"已锁定",published:"已归档"}[v]||"—");
const items=ref([]),archivedReports=ref([]),loading=ref(false),status=ref(""),limited=ref(false),dailyLimit=ref(20),capacitySaving=ref(false),ocrVisible=ref(false),ocrFile=ref(null),ocrLoading=ref(false),selectedAppointment=ref(null),detailVisible=ref(false),current=ref(null),indicators=ref([]);const indicatorForm=reactive({indicator_dict_id:null,value:""});
async function load(){loading.value=true;try{const[appointmentResponse,reportResponse]=await Promise.all([fetchOrgAppointments(status.value?{status:status.value}:{}),fetchOrgReports({status:"published"})]);items.value=appointmentResponse.data.items||[];archivedReports.value=reportResponse.data.items||[];}finally{loading.value=false;}}
async function loadCapacity(){const{data}=await fetchOrgAppointmentCapacity();limited.value=!data.unlimited;if(data.daily_appointment_limit)dailyLimit.value=data.daily_appointment_limit;}
async function saveCapacity(){capacitySaving.value=true;try{await updateOrgAppointmentCapacity(limited.value?dailyLimit.value:null);ElMessage.success(limited.value?`每日上限已设为 ${dailyLimit.value}`:"已设为不限名额");}catch(error){ElMessage.error(error?.response?.data?.message||"保存失败");}finally{capacitySaving.value=false;}}
async function attend(item){try{await ElMessageBox.confirm("确认该用户已经到检？确认后状态变为待上传报告，用户不能再取消。","确认到检",{type:"warning"});await attendOrgAppointment(item.id);ElMessage.success("已确认到检，请上传报告");await load();}catch(error){if(error!=="cancel"&&error!=="close")ElMessage.error(error?.response?.data?.message||"操作失败");}}
async function invalidate(item){try{await ElMessageBox.confirm("标记后不可恢复，也不能再上传报告；用户健康时间线会出现失效提示。","标记已失效",{type:"warning",confirmButtonText:"确认失效"});await invalidateOrgAppointment(item.id);ElMessage.success("预约已失效");await load();}catch(error){if(error!=="cancel"&&error!=="close")ElMessage.error(error?.response?.data?.message||"操作失败");}}
async function createManual(item){try{const{data}=await createOrgReport({appointment_id:item.id});ElMessage.success("报告草稿已创建");await load();await openDetailById(data.item.id);}catch(error){ElMessage.error(error?.response?.data?.message||"创建失败");}}
function openOcr(item){selectedAppointment.value=item;ocrFile.value=null;ocrVisible.value=true;}
async function runOcr(){if(!ocrFile.value){ElMessage.error("请选择报告文件");return;}ocrLoading.value=true;try{const{data}=await uploadOrgReportOcr(ocrFile.value,{appointment_id:selectedAppointment.value.id});ocrVisible.value=false;ElMessage.success(`OCR 草稿已创建，自动映射 ${data.item.indicator_count} 项`);await load();await openDetailById(data.item.id);}catch(error){ElMessage.error(error?.response?.data?.message||"OCR 解析失败");}finally{ocrLoading.value=false;}}
async function openDetailById(id){current.value=(await fetchOrgReport(id)).data.item;detailVisible.value=true;}
async function addIndicator(){try{await addOrgReportIndicator(current.value.id,indicatorForm);indicatorForm.value="";await openDetailById(current.value.id);}catch(error){ElMessage.error(error?.response?.data?.message||"添加失败");}}
async function removeIndicator(item){await deleteOrgReportIndicator(current.value.id,item.id);await openDetailById(current.value.id);}
async function lockReport(id){try{await ElMessageBox.confirm("锁定后报告指标不可修改，确认继续？","确认锁定",{type:"warning"});await lockOrgReport(id);await load();if(detailVisible.value)await openDetailById(id);}catch(error){if(error!=="cancel"&&error!=="close")ElMessage.error(error?.response?.data?.message||"锁定失败");}}
async function submitReport(id){try{await ElMessageBox.confirm("提交后报告永久归档且不可撤下，预约同时变为已履约。","提交并归档",{type:"warning",confirmButtonText:"确认提交"});await submitOrgReport(id);ElMessage.success("报告已归档，预约已履约");detailVisible.value=false;await load();}catch(error){if(error!=="cancel"&&error!=="close")ElMessage.error(error?.response?.data?.message||"提交失败");}}
onMounted(async()=>{const response=await fetchIndicatorDicts();indicators.value=response.data.items||[];indicatorForm.indicator_dict_id=indicators.value[0]?.id;await Promise.all([load(),loadCapacity()]);});
</script>
