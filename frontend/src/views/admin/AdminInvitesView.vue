<template>
  <div class="workspace-page">
    <section class="page-intro"><div><p>机构管理员入驻</p><h2>邀请码管理</h2><span>邀请码单次使用且永不过期；每家机构最多保留一个当前有效邀请码。</span></div></section>
    <el-alert title="安全提示" description="数据库只保存邀请码哈希。明文仅在签发成功时显示一次，请立即复制并通过安全渠道交给对应工作人员。" type="warning" show-icon :closable="false" />
    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon :closable="false" />
    <el-card shadow="never" class="filter-card"><div class="filter-row"><label class="filter-field"><span class="filter-field-label">搜索机构</span><el-input v-model="keyword" clearable placeholder="输入机构名称" /></label><label class="filter-field filter-field--compact"><span class="filter-field-label">邀请码状态</span><el-select v-model="statusFilter"><el-option label="全部邀请码状态" value="all" /><el-option label="未签发" value="none" /><el-option label="有效" value="active" /><el-option label="已使用" value="used" /><el-option label="已撤销" value="revoked" /></el-select></label></div></el-card>
    <el-card shadow="never" class="table-card">
      <el-table :data="filteredRows" v-loading="loading" empty-text="暂无机构">
        <el-table-column label="机构" min-width="220"><template #default="scope"><div class="table-primary"><strong>{{ scope.row.name }}</strong><small>{{ scope.row.branch_name }}</small></div></template></el-table-column>
        <el-table-column label="机构状态" width="110"><template #default="scope"><el-tag :type="scope.row.is_active ? 'success' : 'info'">{{ scope.row.is_active ? "启用" : "停用" }}</el-tag></template></el-table-column>
        <el-table-column label="邀请码状态" width="110"><template #default="scope"><el-tag :type="inviteTag(scope.row.invite?.status)">{{ inviteStatus(scope.row.invite?.status) }}</el-tag></template></el-table-column>
        <el-table-column label="签发时间" min-width="170"><template #default="scope">{{ formatTime(scope.row.invite?.issued_at) }}</template></el-table-column>
        <el-table-column label="使用时间" min-width="170"><template #default="scope">{{ formatTime(scope.row.invite?.used_at) }}</template></el-table-column>
        <el-table-column label="操作" width="210" fixed="right"><template #default="scope"><el-button link type="primary" :disabled="!scope.row.is_active || Boolean(scope.row.administrator)" @click="issue(scope.row)">{{ scope.row.administrator ? "已有管理员" : (scope.row.invite?.status === 'active' ? "重新签发" : "签发邀请码") }}</el-button><el-button v-if="scope.row.invite?.status === 'active' && !scope.row.administrator" link type="danger" @click="revoke(scope.row)">撤销</el-button></template></el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="codeDialogVisible" title="邀请码已签发" width="520px" :close-on-click-modal="false" :close-on-press-escape="false">
      <el-alert title="关闭后将无法再次查看该明文邀请码" type="warning" show-icon :closable="false" />
      <div class="invite-code-box"><small>{{ issuedInstitutionName }}</small><strong>{{ issuedCode }}</strong><el-button type="primary" @click="copyCode">复制邀请码</el-button></div>
      <template #footer><el-button type="primary" @click="codeDialogVisible=false">我已安全保存</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { fetchAdminInstitutions, fetchAdminInvites, issueInstitutionInvite, revokeInstitutionInvite } from "../../api/admin";

const institutions=ref([]),invites=ref([]),loading=ref(false),errorMessage=ref(""),keyword=ref(""),statusFilter=ref("all"),codeDialogVisible=ref(false),issuedCode=ref(""),issuedInstitutionName=ref("");
const rows=computed(()=>{const map=new Map(invites.value.map((item)=>[item.institution_id,item]));return institutions.value.map((item)=>({...item,invite:map.get(item.id)||null}));});
const filteredRows=computed(()=>rows.value.filter((row)=>{const matchesKeyword=`${row.name} ${row.branch_name}`.toLowerCase().includes(keyword.value.trim().toLowerCase());const status=row.invite?.status||"none";return matchesKeyword&&(statusFilter.value==="all"||statusFilter.value===status);}));
const inviteStatus=(status)=>({active:"有效",used:"已使用",revoked:"已撤销",none:"未签发"}[status||"none"]||status);
const inviteTag=(status)=>({active:"success",used:"info",revoked:"danger",none:""}[status||"none"]);
const formatTime=(value)=>value?new Date(value).toLocaleString("zh-CN",{hour12:false}):"-";
async function load(){loading.value=true;errorMessage.value="";try{const[institutionRes,inviteRes]=await Promise.all([fetchAdminInstitutions(),fetchAdminInvites()]);institutions.value=institutionRes.data.items||[];invites.value=inviteRes.data.items||[];}catch(error){errorMessage.value=error?.response?.data?.message||"邀请码信息加载失败";}finally{loading.value=false;}}
async function issue(row){try{if(row.invite?.status==="active")await ElMessageBox.confirm("重新签发会立即使当前邀请码失效，是否继续？","重新签发邀请码",{type:"warning",confirmButtonText:"继续签发",cancelButtonText:"取消"});const{data}=await issueInstitutionInvite(row.id);issuedCode.value=data.invite_code;issuedInstitutionName.value=[row.name,row.branch_name].filter(Boolean).join(" · ");codeDialogVisible.value=true;await load();}catch(error){if(error!=="cancel"&&error!=="close")ElMessage.error(error?.response?.data?.message||"邀请码签发失败");}}
async function revoke(row){try{await ElMessageBox.confirm("撤销后该邀请码将立即无法注册。","撤销邀请码",{type:"warning",confirmButtonText:"确认撤销",cancelButtonText:"取消"});await revokeInstitutionInvite(row.id);ElMessage.success("邀请码已撤销");await load();}catch(error){if(error!=="cancel"&&error!=="close")ElMessage.error(error?.response?.data?.message||"撤销失败");}}
async function copyCode(){try{await navigator.clipboard.writeText(issuedCode.value);ElMessage.success("邀请码已复制");}catch{ElMessage.warning("浏览器无法自动复制，请手动选择邀请码");}}
onMounted(load);
</script>
