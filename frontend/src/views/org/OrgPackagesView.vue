<template>
  <div class="workspace-page">
    <section class="page-intro">
      <div><p>服务项目维护</p><h2>体检套餐</h2><span>所有新增、修改、下架和恢复都需管理员审核，通过后才会生效。</span></div>
      <el-button type="primary" @click="openCreate">新增套餐</el-button>
    </section>
    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon :closable="false" />
    <el-card shadow="never" class="table-card">
      <el-table :data="items" v-loading="loading" empty-text="暂无套餐">
        <el-table-column prop="name" label="套餐名称" min-width="180" />
        <el-table-column prop="focus_area" label="重点方向" min-width="160" />
        <el-table-column label="适用人群" width="120"><template #default="scope">{{ genderLabel(scope.row.gender_scope) }}</template></el-table-column>
        <el-table-column label="价格" width="120"><template #default="scope">¥ {{ Number(scope.row.price || 0).toFixed(2) }}</template></el-table-column>
        <el-table-column label="状态" width="100"><template #default="scope"><el-tag :type="scope.row.is_active ? 'success' : 'info'">{{ scope.row.is_active ? "启用" : "已停用" }}</el-tag></template></el-table-column>
        <el-table-column label="审核" width="110"><template #default="scope"><el-tag v-if="scope.row.pending_request" type="warning">待审核</el-tag><span v-else>—</span></template></el-table-column>
        <el-table-column label="操作" width="190" fixed="right"><template #default="scope"><el-button link type="primary" :disabled="!!scope.row.pending_request" @click="openEdit(scope.row)">编辑</el-button><el-button v-if="scope.row.is_active" link type="danger" :disabled="!!scope.row.pending_request" @click="deactivate(scope.row)">申请下架</el-button><el-button v-else link type="success" :disabled="!!scope.row.pending_request" @click="restore(scope.row)">申请恢复</el-button></template></el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑体检套餐' : '新增体检套餐'" width="600px" :close-on-click-modal="false">
      <el-form :model="form" label-position="top">
        <el-form-item label="套餐名称" required><el-input v-model="form.name" maxlength="120" /></el-form-item>
        <div class="responsive-form-grid">
          <el-form-item label="重点方向" required><el-input v-model="form.focus_area" maxlength="120" placeholder="例如：心脑血管筛查" /></el-form-item>
          <el-form-item label="适用人群" required><el-select v-model="form.gender_scope" style="width:100%"><el-option v-for="option in genderOptions" :key="option.value" :label="option.label" :value="option.value" /></el-select></el-form-item>
          <el-form-item label="价格（元）" required><el-input-number v-model="form.price" :min="0" :precision="2" :step="10" style="width:100%" /></el-form-item>
        </div>
        <el-form-item label="套餐说明"><el-input v-model="form.description" type="textarea" :rows="4" maxlength="1000" show-word-limit /></el-form-item>
      </el-form>
      <template #footer><el-button @click="dialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { createOrgPackage, deactivateOrgPackage, fetchOrgPackages, reactivateOrgPackage, updateOrgPackage } from "../../api/org";

const genderOptions = [{ value: "all", label: "不限" }, { value: "male", label: "男性" }, { value: "female", label: "女性" }, { value: "female_all", label: "女性全龄" }];
const genderLabel = (value) => genderOptions.find((item) => item.value === value)?.label || value || "不限";
const items = ref([]); const loading = ref(false); const saving = ref(false); const errorMessage = ref(""); const dialogVisible = ref(false);
const form = reactive({ id: null, name: "", focus_area: "", gender_scope: "all", price: 0, description: "" });
function reset() { Object.assign(form, { id: null, name: "", focus_area: "", gender_scope: "all", price: 0, description: "" }); }
function openCreate() { reset(); dialogVisible.value = true; }
function openEdit(item) { Object.assign(form, { id: item.id, name: item.name || "", focus_area: item.focus_area || "", gender_scope: item.gender_scope || "all", price: Number(item.price || 0), description: item.description || "" }); dialogVisible.value = true; }
async function load() { loading.value = true; try { const { data } = await fetchOrgPackages(); items.value = data.items || []; } catch (error) { errorMessage.value = error?.response?.data?.message || "套餐列表加载失败"; } finally { loading.value = false; } }
async function save() {
  if (!form.name.trim() || !form.focus_area.trim()) { ElMessage.error("请填写套餐名称和重点方向"); return; }
  saving.value = true;
  const payload = { name: form.name.trim(), focus_area: form.focus_area.trim(), gender_scope: form.gender_scope, price: Number(form.price), description: form.description.trim() || null };
  try { if (form.id) await updateOrgPackage(form.id, payload); else await createOrgPackage(payload); ElMessage.success("变更申请已提交，管理员通过后生效"); dialogVisible.value = false; await load(); }
  catch (error) { ElMessage.error(error?.response?.data?.message || "套餐保存失败"); } finally { saving.value = false; }
}
async function deactivate(item) { try { await ElMessageBox.confirm("提交下架申请后，管理员通过前套餐仍保持当前状态。", "申请下架", { type:"warning", confirmButtonText:"提交申请", cancelButtonText:"取消" }); await deactivateOrgPackage(item.id); ElMessage.success("下架申请已提交"); await load(); } catch (error) { if (error !== "cancel" && error !== "close") ElMessage.error(error?.response?.data?.message || "申请失败"); } }
async function restore(item) { try { await reactivateOrgPackage(item.id); ElMessage.success("恢复申请已提交"); await load(); } catch (error) { ElMessage.error(error?.response?.data?.message || "申请失败"); } }
onMounted(load);
</script>
