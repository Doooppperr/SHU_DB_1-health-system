<template>
  <div class="home-shell">
    <el-card class="home-card">
      <template #header>
        <div class="top-bar">
          <span>个人中心</span>
          <MainNavActions />
        </div>
      </template>

      <el-descriptions :column="1" border>
        <el-descriptions-item label="用户ID">{{ user?.id || '-' }}</el-descriptions-item>
        <el-descriptions-item label="用户名">{{ user?.username || '-' }}</el-descriptions-item>
        <el-descriptions-item label="邮箱">{{ user?.email || '-' }}</el-descriptions-item>
        <el-descriptions-item label="手机号">{{ user?.phone || '-' }}</el-descriptions-item>
        <el-descriptions-item label="角色">{{ user?.role || '-' }}</el-descriptions-item>
      </el-descriptions>

      <el-alert
        v-if="errorMessage"
        style="margin-top: 16px"
        :title="errorMessage"
        type="error"
        :closable="false"
      />
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";

import MainNavActions from "../components/MainNavActions.vue";
import { useAuthStore } from "../stores/auth";

const authStore = useAuthStore();
const router = useRouter();
const errorMessage = ref("");

const user = computed(() => authStore.user);

onMounted(async () => {
  try {
    await authStore.fetchMe();
  } catch (error) {
    errorMessage.value = error?.response?.data?.message || "获取用户信息失败";
  }
});

const goInstitutions = () => {
  router.push({ name: "institutions" });
};

const goRecords = () => {
  router.push({ name: "records" });
};

const goTrends = () => {
  router.push({ name: "trends" });
};

const goFriends = () => {
  router.push({ name: "friends" });
};

const goCommentModeration = () => {
  router.push({ name: "comment-moderation" });
};

const logout = () => {
  authStore.logout();
  router.push({ name: "login" });
};
</script>
