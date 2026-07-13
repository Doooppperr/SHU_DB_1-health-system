<template>
  <main id="main-content" class="result-page" tabindex="-1">
    <div class="result-appearance"><AppearanceQuickControls /></div>
    <div class="result-card">
      <span class="result-code">403</span>
      <h1>当前账号无法访问此页面</h1>
      <p>三类工作台的数据与操作已分开。你可以返回自己角色对应的首页继续使用。</p>
      <el-button type="primary" round @click="goWorkspace">返回我的工作台</el-button>
      <el-button round @click="router.push('/')">返回公开门户</el-button>
    </div>
  </main>
</template>

<script setup>
import { useRouter } from "vue-router";
import AppearanceQuickControls from "../components/AppearanceQuickControls.vue";
import { useAuthStore } from "../stores/auth";
import { dashboardRouteForRole } from "../utils/roles";

const router = useRouter();
const authStore = useAuthStore();
const goWorkspace = () => router.push(dashboardRouteForRole(authStore.user?.role));
</script>
