<template>
  <div class="workspace-page">
    <section class="page-intro">
      <div><p>最多 8 张</p><h2>机构相册</h2><span>拖拽卡片调整顺序，第一张图片会自动成为机构封面。</span></div>
      <div class="page-intro-actions">
        <el-button :disabled="!orderChanged" :loading="ordering" @click="saveOrder">保存排序</el-button>
        <el-button type="primary" :disabled="images.length >= 8" :loading="uploading" @click="fileInput?.click()">上传图片</el-button>
        <input ref="fileInput" hidden type="file" accept="image/jpeg,image/png,image/webp" @change="upload" />
      </div>
    </section>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon :closable="false" />
    <el-alert title="图片要求" description="支持 JPEG、PNG、WebP，每张不超过 5 MB。服务端会验证真实格式、修正方向并移除 EXIF。" type="info" show-icon :closable="false" />

    <el-card class="gallery-card" shadow="never" v-loading="loading">
      <el-empty v-if="!loading && images.length === 0" description="尚未上传机构图片">
        <el-button type="primary" @click="fileInput?.click()">上传第一张图片</el-button>
      </el-empty>
      <div v-else class="gallery-grid">
        <article
          v-for="(item, index) in images"
          :key="item.id"
          class="gallery-item"
          :class="{ 'is-dragging': dragIndex === index }"
          draggable="true"
          @dragstart="dragIndex = index"
          @dragover.prevent
          @drop="dropAt(index)"
          @dragend="dragIndex = null"
        >
          <div class="gallery-image-wrap">
            <img :src="item.image_url" :alt="`机构图片 ${index + 1}`" />
            <el-tag v-if="index === 0" type="success" effect="dark" class="gallery-cover-tag">封面</el-tag>
            <span class="gallery-order">{{ index + 1 }}</span>
          </div>
          <div class="gallery-item-actions">
            <span>按住拖拽排序</span>
            <div><el-button link :disabled="index === 0" @click="move(index, -1)">前移</el-button><el-button link :disabled="index === images.length - 1" @click="move(index, 1)">后移</el-button><el-button link type="danger" @click="remove(item)">删除</el-button></div>
          </div>
        </article>
        <button v-if="images.length < 8" type="button" class="gallery-add" @click="fileInput?.click()"><span>＋</span><strong>继续上传</strong><small>{{ images.length }}/8 张</small></button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { deleteOrgImage, fetchOrgImages, reorderOrgImages, uploadOrgImage } from "../../api/org";

const fileInput = ref(null);
const images = ref([]);
const loading = ref(false);
const uploading = ref(false);
const ordering = ref(false);
const errorMessage = ref("");
const dragIndex = ref(null);
const orderChanged = ref(false);

function sorted(items) { return [...items].sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0)); }
async function load() {
  loading.value = true;
  try {
    const { data } = await fetchOrgImages();
    images.value = sorted(data.items || data.images || []);
    orderChanged.value = false;
  } catch (error) {
    errorMessage.value = error?.response?.data?.message || "机构相册加载失败";
  } finally { loading.value = false; }
}
function move(index, delta) {
  const target = index + delta;
  if (target < 0 || target >= images.value.length) return;
  const next = [...images.value];
  [next[index], next[target]] = [next[target], next[index]];
  images.value = next;
  orderChanged.value = true;
}
function dropAt(targetIndex) {
  if (dragIndex.value === null || dragIndex.value === targetIndex) return;
  const next = [...images.value];
  const [moved] = next.splice(dragIndex.value, 1);
  next.splice(targetIndex, 0, moved);
  images.value = next;
  orderChanged.value = true;
  dragIndex.value = null;
}
async function upload(event) {
  const file = event.target.files?.[0];
  event.target.value = "";
  if (!file) return;
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) { ElMessage.error("仅支持 JPEG、PNG 或 WebP 图片"); return; }
  if (file.size > 5 * 1024 * 1024) { ElMessage.error("单张图片不能超过 5 MB"); return; }
  if (images.value.length >= 8) { ElMessage.warning("每家机构最多上传 8 张图片"); return; }
  uploading.value = true;
  try {
    await uploadOrgImage(file);
    ElMessage.success("图片已上传");
    await load();
  } catch (error) { ElMessage.error(error?.response?.data?.message || "图片上传失败"); }
  finally { uploading.value = false; }
}
async function saveOrder() {
  ordering.value = true;
  try {
    await reorderOrgImages(images.value.map((item) => item.id));
    ElMessage.success("图片顺序已保存");
    await load();
  } catch (error) { ElMessage.error(error?.response?.data?.message || "排序保存失败"); }
  finally { ordering.value = false; }
}
async function remove(item) {
  try {
    await ElMessageBox.confirm("删除后无法恢复，确定删除这张机构图片？", "删除图片", { type: "warning", confirmButtonText: "删除", cancelButtonText: "取消" });
    await deleteOrgImage(item.id);
    ElMessage.success("图片已删除");
    await load();
  } catch (error) { if (error !== "cancel" && error !== "close") ElMessage.error(error?.response?.data?.message || "删除失败"); }
}
onMounted(load);
</script>
