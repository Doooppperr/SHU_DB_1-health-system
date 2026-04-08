<template>
  <div class="top-actions wrap-actions">
    <slot name="prefix" />

    <el-button
      v-for="item in navItems"
      :key="item.name"
      :type="item.name === activeRouteName ? 'primary' : 'default'"
      :plain="item.name !== activeRouteName"
      @click="go(item.name)"
    >
      {{ item.label }}
    </el-button>

    <slot name="suffix" />
    <el-button type="danger" plain @click="logout">退出登录</el-button>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";

import { useAuthStore } from "../stores/auth";

const router = useRouter();
const route = useRoute();
const authStore = useAuthStore();

const navItems = computed(() => {
  const commonItems = [
    { name: "institutions", label: "机构列表" },
    { name: "records", label: "体检档案" },
    { name: "record-upload", label: "OCR上传" },
    { name: "friends", label: "亲友管理" },
    { name: "trends", label: "指标趋势" },
    { name: "my-comments", label: "我的评论" },
    { name: "profile", label: "个人中心" },
  ];

  if (authStore.user?.role === "admin") {
    commonItems.splice(6, 0, { name: "comment-moderation", label: "评论审核" });
    commonItems.splice(7, 0, { name: "user-management", label: "用户管理" });
  }

  return commonItems;
});

const activeRouteName = computed(() => {
  if (route.name === "institution-detail") {
    return "institutions";
  }
  if (route.name === "record-detail") {
    return "records";
  }
  return route.name;
});

const go = (name) => {
  if (route.name === name) {
    return;
  }
  router.push({ name });
};

const logout = () => {
  authStore.logout();
  router.push({ name: "login" });
};
</script>
