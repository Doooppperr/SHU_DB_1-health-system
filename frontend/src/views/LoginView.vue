<template>
  <div class="page-shell">
    <el-card class="auth-card">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>登录</span>
          <el-button link type="primary" @click="goRegister">去注册</el-button>
        </div>
      </template>

      <el-form :model="form" label-position="top" @submit.prevent="onSubmit">
        <el-form-item label="用户名">
          <el-input v-model="form.username" placeholder="请输入用户名" />
        </el-form-item>

        <el-form-item label="密码">
          <el-input v-model="form.password" show-password placeholder="请输入密码" />
        </el-form-item>

        <el-alert v-if="errorMessage" :title="errorMessage" type="error" :closable="false" style="margin-bottom: 12px" />

        <el-button type="primary" :loading="loading" style="width: 100%" @click="onSubmit">
          登录
        </el-button>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref } from "vue";
import { useRouter } from "vue-router";

import { useAuthStore } from "../stores/auth";

const router = useRouter();
const authStore = useAuthStore();

const form = reactive({
  username: "",
  password: "",
});

const loading = ref(false);
const errorMessage = ref("");

const onSubmit = async () => {
  if (!form.username || !form.password) {
    errorMessage.value = "请输入用户名和密码";
    return;
  }

  loading.value = true;
  errorMessage.value = "";

  try {
    await authStore.loginUser(form);
    await authStore.fetchMe();
    router.push({ name: "institutions" });
  } catch (error) {
    errorMessage.value = error?.response?.data?.message || "登录失败，请重试";
  } finally {
    loading.value = false;
  }
};

const goRegister = () => {
  router.push({ name: "register" });
};
</script>
