<template>
  <div class="home-shell">
    <el-card class="home-card">
      <template #header>
        <div class="top-bar">
          <span>评论审核</span>
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

      <el-table v-if="!forbiddenMessage" :data="comments" border v-loading="loading" empty-text="暂无评论数据">
        <el-table-column label="机构" min-width="220">
          <template #default="scope">
            {{ scope.row.institution?.name }} · {{ scope.row.institution?.branch_name }}
          </template>
        </el-table-column>
        <el-table-column label="用户" min-width="120">
          <template #default="scope">
            {{ scope.row.user?.username || "-" }}
          </template>
        </el-table-column>
        <el-table-column prop="rating" label="评分" width="90" />
        <el-table-column prop="content" label="评论内容" min-width="320" />
        <el-table-column prop="created_at" label="提交时间" min-width="180" />
        <el-table-column label="可见" width="110">
          <template #default="scope">
            <el-switch
              :model-value="scope.row.is_visible"
              :active-value="true"
              :inactive-value="false"
              @change="(value) => toggleVisibility(scope.row, value)"
            />
          </template>
        </el-table-column>
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
import { deleteComment, fetchCommentModerationList, updateCommentVisibility } from "../api/comments";

const loading = ref(false);
const comments = ref([]);
const errorMessage = ref("");
const forbiddenMessage = ref("");

const loadComments = async () => {
  loading.value = true;
  errorMessage.value = "";
  forbiddenMessage.value = "";

  try {
    const { data } = await fetchCommentModerationList();
    comments.value = data.items || [];
  } catch (error) {
    if (error?.response?.status === 403) {
      forbiddenMessage.value = "仅管理员可以访问评论审核。";
      comments.value = [];
    } else {
      errorMessage.value = error?.response?.data?.message || "评论审核数据加载失败";
    }
  } finally {
    loading.value = false;
  }
};

const toggleVisibility = async (row, isVisible) => {
  try {
    await updateCommentVisibility(row.id, { is_visible: isVisible });
    row.is_visible = isVisible;
    ElMessage.success(isVisible ? "评论已显示" : "评论已隐藏");
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || "可见性更新失败");
    await loadComments();
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
