import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it } from "vitest";

import AiAssistantLauncher from "./AiAssistantLauncher.vue";
import { useAiChatStore } from "../stores/aiChat";
import { useAuthStore } from "../stores/auth";

beforeEach(()=>{localStorage.clear();sessionStorage.clear();});

describe("AiAssistantLauncher",()=>{
  function mountLauncher(role="user") { const pinia=createPinia();setActivePinia(pinia);const auth=useAuthStore(pinia);auth.user={id:1,role};const wrapper=mount(AiAssistantLauncher,{global:{plugins:[pinia]}});return{wrapper,aiStore:useAiChatStore(pinia)}; }

  it("opens and closes the assistant from a stable topbar button",async()=>{const{wrapper,aiStore}=mountLauncher();const button=wrapper.get("button");expect(button.text()).toContain("AI 健康助手");expect(button.attributes("aria-expanded")).toBe("false");await button.trigger("click");expect(aiStore.isOpen).toBe(true);expect(button.text()).toContain("收起助手");expect(button.attributes("aria-expanded")).toBe("true");});
  it("is only available in the personal health workspace",()=>{const{wrapper}=mountLauncher("institution_admin");expect(wrapper.find("button").exists()).toBe(false);});
});
