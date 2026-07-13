<template>
  <main id="main-content" class="result-page" tabindex="-1">
    <div class="result-appearance"><AppearanceQuickControls /></div>
    <div class="result-card">
      <span class="result-code">404</span>
      <h1>没有找到这个页面</h1>
      <p>页面地址可能已变更，返回门户或工作台即可继续。</p>
      <el-button type="primary" round @click="goHome">返回首页</el-button>
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
function goHome() {
  router.push(authStore.accessToken ? dashboardRouteForRole(authStore.user?.role) : { name: "public-home" });
}
</script>
