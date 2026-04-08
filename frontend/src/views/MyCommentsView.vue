<template>
  <div class="home-shell">
    <el-card class="home-card">
      <template #header>
        <div class="top-bar">
          <span>我的评论</span>
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

      <el-table :data="comments" border v-loading="loading" empty-text="暂无评论记录">
        <el-table-column label="机构" min-width="220">
          <template #default="scope">
            {{ scope.row.institution?.name }} · {{ scope.row.institution?.branch_name }}
          </template>
        </el-table-column>
        <el-table-column label="评分" width="110">
          <template #default="scope">
            <el-rate :model-value="scope.row.rating" disabled />
          </template>
        </el-table-column>
        <el-table-column prop="content" label="评论内容" min-width="320" />
        <el-table-column label="状态" width="110">
          <template #default="scope">
            <el-tag :type="scope.row.is_visible ? 'success' : 'warning'">
              {{ scope.row.is_visible ? "已公开" : "待审核" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="提交时间" min-width="180" />
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="scope">
            <el-button type="danger" link @click="removeComment(scope.row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";

import MainNavActions from "../components/MainNavActions.vue";
import { deleteComment, fetchMyComments } from "../api/comments";

const loading = ref(false);
const comments = ref([]);
const errorMessage = ref("");

const loadComments = async () => {
  loading.value = true;
  errorMessage.value = "";

  try {
    const { data } = await fetchMyComments();
    comments.value = data.items || [];
  } catch (error) {
    errorMessage.value = error?.response?.data?.message || "我的评论加载失败";
  } finally {
    loading.value = false;
  }
};

const removeComment = async (row) => {
  try {
    await ElMessageBox.confirm("删除后不可恢复，确认删除该评论？", "提示", {
      type: "warning",
      confirmButtonText: "确认删除",
      cancelButtonText: "取消",
    });
    await deleteComment(row.id);
    ElMessage.success("评论已删除");
    await loadComments();
  } catch (error) {
    if (error === "cancel") {
      return;
    }
    ElMessage.error(error?.response?.data?.message || "评论删除失败");
  }
};

onMounted(async () => {
  await loadComments();
});
</script>
