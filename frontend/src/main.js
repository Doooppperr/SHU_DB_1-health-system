import { createApp } from "vue";
import ElementPlus from "element-plus";
import "element-plus/dist/index.css";
import "element-plus/theme-chalk/dark/css-vars.css";

import App from "./App.vue";
import { createPinia } from "pinia";
import router from "./router";
import { useAppearanceStore } from "./stores/appearance";
import "./style.css";
import "./user-platform.css";

const app = createApp(App);
const pinia = createPinia();

app.use(pinia);
useAppearanceStore(pinia).initialize();
app.use(router);
app.use(ElementPlus);

app.mount("#app");
