<template>
  <div class="page-shell">
    <el-card class="auth-card">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>注册</span>
          <el-button link type="primary" @click="goLogin">去登录</el-button>
        </div>
      </template>

      <el-form :model="form" label-position="top" @submit.prevent="onSubmit">
        <el-form-item label="用户名">
          <el-input v-model="form.username" placeholder="请输入用户名" />
        </el-form-item>

        <el-form-item label="邮箱">
          <el-input v-model="form.email" placeholder="请输入邮箱（可选）" />
        </el-form-item>

        <el-form-item label="手机号">
          <el-input v-model="form.phone" placeholder="请输入手机号（可选）" />
        </el-form-item>

        <el-form-item label="密码">
          <el-input v-model="form.password" show-password placeholder="至少6位密码" />
        </el-form-item>

        <el-alert v-if="errorMessage" :title="errorMessage" type="error" :closable="false" style="margin-bottom: 12px" />

        <el-button type="primary" :loading="loading" style="width: 100%" @click="onSubmit">
          注册
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
  email: "",
  phone: "",
  password: "",
});

const loading = ref(false);
const errorMessage = ref("");

const onSubmit = async () => {
  if (!form.username || !form.password) {
    errorMessage.value = "用户名和密码为必填项";
    return;
  }

  loading.value = true;
  errorMessage.value = "";

  try {
    await authStore.registerUser(form);
    await authStore.loginUser({ username: form.username, password: form.password });
    await authStore.fetchMe();
    router.push({ name: "institutions" });
  } catch (error) {
    errorMessage.value = error?.response?.data?.message || "注册失败，请重试";
  } finally {
    loading.value = false;
  }
};

const goLogin = () => {
  router.push({ name: "login" });
};
</script>
