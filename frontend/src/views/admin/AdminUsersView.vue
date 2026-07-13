<template>
  <div class="workspace-page">
    <section class="page-intro"><div><p>账号与权限</p><h2>用户与角色管理</h2><span>机构管理员只能通过邀请码产生，不能在通用用户编辑中直接赋予。</span></div></section>
    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon :closable="false" />
    <el-card shadow="never" class="filter-card"><div class="filter-row"><label class="filter-field"><span class="filter-field-label">搜索用户</span><el-input v-model="keyword" clearable placeholder="用户名、邮箱或手机号" /></label><label class="filter-field filter-field--compact"><span class="filter-field-label">角色</span><el-select v-model="roleFilter"><el-option label="全部角色" value="all" /><el-option label="普通用户" value="user" /><el-option label="机构管理员" value="institution_admin" /><el-option label="系统管理员" value="admin" /></el-select></label></div></el-card>
    <el-card shadow="never" class="table-card">
      <el-table :data="filteredItems" v-loading="loading" empty-text="暂无用户">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column label="账号" min-width="170"><template #default="scope"><div class="table-primary"><strong>{{ scope.row.username }}</strong><small>{{ scope.row.email || "未填写邮箱" }}</small></div></template></el-table-column>
        <el-table-column prop="phone" label="手机号" min-width="130"><template #default="scope">{{ scope.row.phone || "-" }}</template></el-table-column>
        <el-table-column label="角色" width="130"><template #default="scope"><el-tag :type="roleTag(scope.row.role)">{{ roleLabel(scope.row.role) }}</el-tag></template></el-table-column>
        <el-table-column label="绑定机构" min-width="210"><template #default="scope">{{ institutionName(scope.row) }}</template></el-table-column>
        <el-table-column label="注册时间" min-width="170"><template #default="scope">{{ formatTime(scope.row.created_at) }}</template></el-table-column>
        <el-table-column label="操作" width="230" fixed="right"><template #default="scope"><el-button link type="primary" @click="openEdit(scope.row)">编辑</el-button><el-button v-if="scope.row.role === 'institution_admin'" link type="warning" @click="revokeManager(scope.row)">撤销机构管理员</el-button><el-button v-else-if="scope.row.id !== authStore.user?.id" link type="danger" @click="remove(scope.row)">删除</el-button></template></el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" title="编辑用户" width="560px" :close-on-click-modal="false">
      <el-form :model="form" label-position="top">
        <el-form-item label="用户名" required><el-input v-model="form.username" /></el-form-item>
        <div class="responsive-form-grid"><el-form-item label="邮箱"><el-input v-model="form.email" /></el-form-item><el-form-item label="手机号"><el-input v-model="form.phone" /></el-form-item></div>
        <el-form-item label="角色">
          <template v-if="form.originalRole === 'institution_admin'"><el-input model-value="机构管理员（需使用专用撤销操作变更）" disabled /></template>
          <el-select v-else v-model="form.role" style="width:100%"><el-option label="普通用户" value="user" /><el-option label="系统管理员" value="admin" /></el-select>
          <p class="auth-field-tip">机构管理员身份与机构绑定只能由邀请码建立。</p>
        </el-form-item>
        <el-form-item label="重置密码（可选）"><el-input v-model="form.password" type="password" show-password placeholder="留空则不修改，至少 6 位" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="dialogVisible=false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { revokeInstitutionAdmin } from "../../api/admin";
import { deleteUser, fetchUsers, updateUser } from "../../api/users";
import { useAuthStore } from "../../stores/auth";
import { roleLabel } from "../../utils/roles";

const authStore=useAuthStore();const items=ref([]),loading=ref(false),saving=ref(false),errorMessage=ref(""),keyword=ref(""),roleFilter=ref("all"),dialogVisible=ref(false);const form=reactive({id:null,username:"",email:"",phone:"",role:"user",originalRole:"user",password:""});
const filteredItems=computed(()=>items.value.filter((item)=>{const text=`${item.username} ${item.email||""} ${item.phone||""}`.toLowerCase();return text.includes(keyword.value.trim().toLowerCase())&&(roleFilter.value==="all"||item.role===roleFilter.value);}));
const roleTag=(role)=>({user:"",institution_admin:"warning",admin:"danger"}[role]||"info");
const institutionName=(item)=>item.managed_institution?[item.managed_institution.name,item.managed_institution.branch_name].filter(Boolean).join(" · "):"-";
const formatTime=(value)=>value?new Date(value).toLocaleString("zh-CN",{hour12:false}):"-";
async function load(){loading.value=true;errorMessage.value="";try{const{data}=await fetchUsers();items.value=data.items||[];}catch(error){errorMessage.value=error?.response?.data?.message||"用户列表加载失败";}finally{loading.value=false;}}
function openEdit(item){Object.assign(form,{id:item.id,username:item.username||"",email:item.email||"",phone:item.phone||"",role:item.role,originalRole:item.role,password:""});dialogVisible.value=true;}
async function save(){if(!form.username.trim()){ElMessage.error("用户名不能为空");return;}if(form.password&&form.password.length<6){ElMessage.error("新密码至少 6 位");return;}saving.value=true;const payload={username:form.username.trim(),email:form.email.trim()||null,phone:form.phone.trim()||null};if(form.originalRole!=="institution_admin")payload.role=form.role;if(form.password)payload.password=form.password;try{await updateUser(form.id,payload);ElMessage.success("用户资料已更新");dialogVisible.value=false;await load();if(form.id===authStore.user?.id)await authStore.fetchMe();}catch(error){ElMessage.error(error?.response?.data?.message||"保存失败");}finally{saving.value=false;}}
async function revokeManager(item){try{await ElMessageBox.confirm(`撤销后，${item.username} 将降级为普通用户并立即失去 ${institutionName(item)} 的后台权限。账号和历史个人数据会保留。`,`撤销机构管理员`,{type:"warning",confirmButtonText:"确认撤销",cancelButtonText:"取消"});await revokeInstitutionAdmin(item.id);ElMessage.success("机构管理员已撤销");await load();}catch(error){if(error!=="cancel"&&error!=="close")ElMessage.error(error?.response?.data?.message||"撤销失败");}}
async function remove(item){try{await ElMessageBox.confirm(`删除账号 ${item.username} 及其关联个人数据？此操作无法恢复。`,`删除用户`,{type:"warning",confirmButtonText:"确认删除",cancelButtonText:"取消"});await deleteUser(item.id);ElMessage.success("用户已删除");await load();}catch(error){if(error!=="cancel"&&error!=="close")ElMessage.error(error?.response?.data?.message||"删除失败");}}
onMounted(load);
</script>
