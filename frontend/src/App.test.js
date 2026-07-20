import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("vue-router", () => ({ useRoute: () => ({ name: "dashboard", fullPath: "/dashboard" }) }));

import App from "./App.vue";
import { useAiChatStore } from "./stores/aiChat";
import { useAuthStore } from "./stores/auth";

const wrappers=[];
const originalInnerWidth=window.innerWidth;
const originalClientWidth=document.documentElement.clientWidth;

function setViewport(width){Object.defineProperty(window,"innerWidth",{configurable:true,writable:true,value:width});Object.defineProperty(document.documentElement,"clientWidth",{configurable:true,value:width});}
function mountUserApp(width=1440){setViewport(width);const pinia=createPinia();setActivePinia(pinia);const wrapper=mount(App,{global:{plugins:[pinia],stubs:{AiAssistant:{props:["overlayMode"],template:'<aside data-testid="ai-panel" :data-overlay="String(overlayMode)" />'},RouterView:{template:'<main id="main-content" tabindex="-1" />'}}}});wrappers.push(wrapper);const authStore=useAuthStore(pinia);authStore.accessToken="token";authStore.user={id:1,username:"test1",role:"user"};const aiStore=useAiChatStore(pinia);return{wrapper,aiStore,authStore};}

beforeEach(()=>{localStorage.clear();sessionStorage.clear();setViewport(1440);});
afterEach(()=>{wrappers.splice(0).forEach((wrapper)=>wrapper.unmount());setViewport(originalInnerWidth);Object.defineProperty(document.documentElement,"clientWidth",{configurable:true,value:originalClientWidth});});

describe("App AI workspace layout",()=>{
  it("reserves a real desktop column without publishing zoom canvas variables",async()=>{
    const{wrapper,aiStore}=mountUserApp(1440);aiStore.setPanelWidth(520);aiStore.setOpen(true);await wrapper.vm.$nextTick();
    const shell=wrapper.get(".app-with-ai");
    expect(shell.classes()).toContain("ai-panel-active");
    expect(shell.element.style.getPropertyValue("--ai-panel-width")).toBe("520px");
    expect(shell.element.style.getPropertyValue("--ai-stage-scale")).toBe("");
    expect(wrapper.get(".app-route-stage").attributes("inert")).toBeUndefined();
    expect(wrapper.get('[data-testid="ai-panel"]').attributes("data-overlay")).toBe("false");
  });

  it("uses an accessible overlay on compact workspaces instead of scaling the page",async()=>{
    const{wrapper,aiStore}=mountUserApp(900);aiStore.setOpen(true);await wrapper.vm.$nextTick();
    const stage=wrapper.get(".app-route-stage");
    expect(stage.attributes("inert")).toBe("");
    expect(stage.attributes("aria-hidden")).toBe("true");
    expect(wrapper.get('[data-testid="ai-panel"]').attributes("data-overlay")).toBe("true");
    expect(wrapper.get(".app-with-ai").element.style.zoom).toBe("");
  });

  it("does not mount the personal health assistant in an institution workspace",async()=>{
    const{wrapper,authStore}=mountUserApp();authStore.user={id:9,username:"institution1_staff1",role:"institution_admin"};await wrapper.vm.$nextTick();
    expect(wrapper.find('[data-testid="ai-panel"]').exists()).toBe(false);
  });
});
