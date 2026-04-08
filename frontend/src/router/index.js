import { createRouter, createWebHistory } from "vue-router";

import { useAuthStore } from "../stores/auth";

const LoginView = () => import("../views/LoginView.vue");
const RegisterView = () => import("../views/RegisterView.vue");
const InstitutionListView = () => import("../views/InstitutionListView.vue");
const InstitutionDetailView = () => import("../views/InstitutionDetailView.vue");
const RecordListView = () => import("../views/RecordListView.vue");
const RecordOcrUploadView = () => import("../views/RecordOcrUploadView.vue");
const RecordDetailView = () => import("../views/RecordDetailView.vue");
const FriendManageView = () => import("../views/FriendManageView.vue");
const TrendView = () => import("../views/TrendView.vue");
const CommentModerationView = () => import("../views/CommentModerationView.vue");
const MyCommentsView = () => import("../views/MyCommentsView.vue");
const UserManageView = () => import("../views/UserManageView.vue");
const HomeView = () => import("../views/HomeView.vue");

const routes = [
  {
    path: "/",
    redirect: "/institutions",
  },
  {
    path: "/institutions",
    name: "institutions",
    component: InstitutionListView,
    meta: { requiresAuth: true },
  },
  {
    path: "/institutions/:id",
    name: "institution-detail",
    component: InstitutionDetailView,
    meta: { requiresAuth: true },
  },
  {
    path: "/records",
    name: "records",
    component: RecordListView,
    meta: { requiresAuth: true },
  },
  {
    path: "/records/upload",
    name: "record-upload",
    component: RecordOcrUploadView,
    meta: { requiresAuth: true },
  },
  {
    path: "/records/:id",
    name: "record-detail",
    component: RecordDetailView,
    meta: { requiresAuth: true },
  },
  {
    path: "/friends",
    name: "friends",
    component: FriendManageView,
    meta: { requiresAuth: true },
  },
  {
    path: "/trends",
    name: "trends",
    component: TrendView,
    meta: { requiresAuth: true },
  },
  {
    path: "/admin/comments",
    name: "comment-moderation",
    component: CommentModerationView,
    meta: { requiresAuth: true },
  },
  {
    path: "/comments/mine",
    name: "my-comments",
    component: MyCommentsView,
    meta: { requiresAuth: true },
  },
  {
    path: "/admin/users",
    name: "user-management",
    component: UserManageView,
    meta: { requiresAuth: true },
  },
  {
    path: "/profile",
    name: "profile",
    component: HomeView,
    meta: { requiresAuth: true },
  },
  {
    path: "/login",
    name: "login",
    component: LoginView,
    meta: { guestOnly: true },
  },
  {
    path: "/register",
    name: "register",
    component: RegisterView,
    meta: { guestOnly: true },
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach(async (to) => {
  const authStore = useAuthStore();
  authStore.hydrate();

  if (to.meta.requiresAuth) {
    if (!authStore.accessToken) {
      const refreshed = await authStore.tryRefresh();
      if (!refreshed) {
        return { name: "login" };
      }
    }

    return true;
  }

  if (to.meta.guestOnly && authStore.accessToken) {
    return { name: "institutions" };
  }

  return true;
});

export default router;
