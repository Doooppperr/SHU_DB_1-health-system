<template>
  <div class="home-shell">
    <el-card class="home-card">
      <template #header>
        <div class="top-bar">
          <span>用户管理</span>
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

      <el-alert
        v-if="forbiddenMessage"
        :title="forbiddenMessage"
        type="warning"
        :closable="false"
        style="margin-bottom: 16px"
      />

      <el-table v-if="!forbiddenMessage" :data="users" border v-loading="loading" empty-text="暂无用户数据">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="username" label="用户名" min-width="140" />
        <el-table-column prop="email" label="邮箱" min-width="220" />
        <el-table-column prop="phone" label="手机号" min-width="140" />
        <el-table-column prop="role" label="角色" width="110" />
        <el-table-column prop="created_at" label="创建时间" min-width="180" />
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="scope">
            <el-button type="primary" link @click="openEditDialog(scope.row)">修改</el-button>
            <el-button type="danger" link @click="removeUser(scope.row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="editDialogVisible" title="修改用户" width="560px" :close-on-click-modal="false">
      <el-form :model="editForm" label-width="84px">
        <el-form-item label="用户名" required>
          <el-input v-model="editForm.username" maxlength="80" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="editForm.email" maxlength="120" placeholder="留空表示清空邮箱" />
        </el-form-item>
        <el-form-item label="手机号">
          <el-input v-model="editForm.phone" maxlength="30" placeholder="留空表示清空手机号" />
        </el-form-item>
        <el-form-item label="角色" required>
          <el-select v-model="editForm.role" style="width: 100%">
            <el-option label="user" value="user" />
            <el-option label="admin" value="admin" />
          </el-select>
        </el-form-item>
        <el-form-item label="新密码">
          <el-input
            v-model="editForm.password"
            show-password
            maxlength="128"
            placeholder="不修改密码可留空（修改时至少6位）"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="editSubmitting" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";

import MainNavActions from "../components/MainNavActions.vue";
import { deleteUser, fetchUsers, updateUser } from "../api/users";
import { useAuthStore } from "../stores/auth";

const authStore = useAuthStore();

const loading = ref(false);
const users = ref([]);
const errorMessage = ref("");
const forbiddenMessage = ref("");
const editDialogVisible = ref(false);
const editSubmitting = ref(false);

const editForm = reactive({
  id: null,
  username: "",
  email: "",
  phone: "",
  role: "user",
  password: "",
});

const loadUsers = async () => {
  loading.value = true;
  errorMessage.value = "";
  forbiddenMessage.value = "";

  try {
    const { data } = await fetchUsers();
    users.value = data.items || [];
  } catch (error) {
    if (error?.response?.status === 403) {
      forbiddenMessage.value = "仅管理员可以访问用户管理。";
      users.value = [];
    } else {
      errorMessage.value = error?.response?.data?.message || "用户列表加载失败";
    }
  } finally {
    loading.value = false;
  }
};

const openEditDialog = (row) => {
  editForm.id = row.id;
  editForm.username = row.username || "";
  editForm.email = row.email || "";
  editForm.phone = row.phone || "";
  editForm.role = row.role || "user";
  editForm.password = "";
  editDialogVisible.value = true;
};

const submitEdit = async () => {
  if (!editForm.id) {
    return;
  }
  if (!editForm.username.trim()) {
    ElMessage.error("用户名不能为空");
    return;
  }
  if (editForm.password && editForm.password.length < 6) {
    ElMessage.error("新密码至少 6 位");
    return;
  }

  editSubmitting.value = true;
  try {
    const payload = {
      username: editForm.username.trim(),
      email: editForm.email.trim(),
      phone: editForm.phone.trim(),
      role: editForm.role,
    };
    if (editForm.password) {
      payload.password = editForm.password;
    }

    await updateUser(editForm.id, payload);
    ElMessage.success("用户已更新");
    editDialogVisible.value = false;
    await loadUsers();

    if (authStore.user?.id === editForm.id) {
      await authStore.fetchMe();
    }
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || "用户更新失败");
  } finally {
    editSubmitting.value = false;
  }
};

const removeUser = async (row) => {
  try {
    await ElMessageBox.confirm(`确认删除用户 ${row.username}？删除后不可恢复。`, "提示", {
      type: "warning",
      confirmButtonText: "确认删除",
      cancelButtonText: "取消",
    });

    await deleteUser(row.id);
    ElMessage.success("用户已删除");
    await loadUsers();
  } catch (error) {
    if (error === "cancel") {
      return;
    }
    ElMessage.error(error?.response?.data?.message || "用户删除失败");
  }
};

onMounted(async () => {
  await loadUsers();
});
</script>
