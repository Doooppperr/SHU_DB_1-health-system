<template>
  <div class="workspace-page user-platform-page institution-directory">
    <section class="user-page-lead">
      <div><span class="user-kicker">体检服务网络</span><h2>先选机构，再选方便到达的分院</h2><p>同一机构的分院共享已归档体检资料，但预约时间、名额和套餐仍由各分院独立安排。</p></div>
      <el-button type="primary" plain @click="router.push({name:'appointments'})">查看我的预约</el-button>
    </section>
    <el-alert v-if="errorMessage" :title="errorMessage" type="error" :closable="false" show-icon/>
    <section v-loading="loading" class="organization-list">
      <article v-for="organization in organizations" :key="organization.id" class="organization-card">
        <header><div><span>机构主体</span><h3>{{organization.name}}</h3><p>{{organization.description}}</p></div><el-tag type="success">{{organization.branches.length}} 家分院</el-tag></header>
        <div class="organization-features"><span v-for="feature in organization.service_features" :key="feature">{{feature}}</span></div>
        <div class="branch-grid">
          <button v-for="branch in organization.branches" :key="branch.id" type="button" class="branch-card" @click="goDetail(branch.id)">
            <InstitutionCoverImage :institution="branch"/>
            <span><strong>{{branch.branch_name}}</strong><small>{{branch.district}} · {{branch.address}}</small><small>{{branch.package_count}} 个可预约套餐</small></span><b>查看分院 ›</b>
          </button>
        </div>
      </article>
      <el-empty v-if="!loading&&!organizations.length" description="暂无可预约机构"/>
    </section>
  </div>
</template>

<script setup>
import {onMounted,ref} from "vue";
import {useRouter} from "vue-router";
import InstitutionCoverImage from "../components/InstitutionCoverImage.vue";
import {fetchOrganizations} from "../api/institutions";
const router=useRouter(),loading=ref(false),organizations=ref([]),errorMessage=ref("");
async function load(){loading.value=true;try{organizations.value=(await fetchOrganizations()).data.items||[];}catch(error){errorMessage.value=error?.response?.data?.message||"机构列表加载失败";}finally{loading.value=false;}}
function goDetail(id){router.push({name:"institution-detail",params:{id}});}
onMounted(load);
</script>

<style scoped>
.organization-list{display:grid;gap:20px}.organization-card{padding:24px;border:1px solid var(--color-border);border-radius:18px;background:var(--color-surface)}.organization-card>header{display:flex;justify-content:space-between;gap:20px}.organization-card h3{margin:4px 0 8px;font-size:24px}.organization-card p{margin:0;color:var(--color-muted);line-height:1.7}.organization-card header span{color:var(--workspace-accent);font-size:12px;font-weight:800}.organization-features{display:flex;flex-wrap:wrap;gap:8px;margin:16px 0}.organization-features span{padding:6px 10px;border-radius:999px;background:var(--color-soft);color:var(--workspace-accent)}.branch-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.branch-card{display:grid;gap:10px;padding:0 0 14px;overflow:hidden;border:1px solid var(--color-border);border-radius:14px;background:transparent;color:inherit;text-align:left;cursor:pointer}.branch-card>span,.branch-card>b{padding:0 14px}.branch-card strong,.branch-card small{display:block}.branch-card small{margin-top:5px;color:var(--color-muted)}.branch-card b{color:var(--workspace-accent)}@media(max-width:1000px){.branch-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:640px){.branch-grid{grid-template-columns:1fr}.organization-card{padding:18px}}
</style>
