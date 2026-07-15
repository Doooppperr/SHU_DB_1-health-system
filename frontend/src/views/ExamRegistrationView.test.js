import { flushPromises, mount } from "@vue/test-utils";
import ElementPlus from "element-plus";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  fetchInstitutions: vi.fn(),
  fetchInstitutionPackages: vi.fn(),
  fetchRegistrations: vi.fn(),
  createRegistration: vi.fn(),
  cancelRegistration: vi.fn(),
}));
const routeState = vi.hoisted(() => ({ query: {} }));

vi.mock("../api/institutions", () => ({
  fetchInstitutions: api.fetchInstitutions,
  fetchInstitutionPackages: api.fetchInstitutionPackages,
}));
vi.mock("../api/health", () => ({
  fetchRegistrations: api.fetchRegistrations,
  createRegistration: api.createRegistration,
  cancelRegistration: api.cancelRegistration,
}));
vi.mock("vue-router", () => ({ useRoute: () => routeState }));

import ExamRegistrationView from "./ExamRegistrationView.vue";

const wrappers = [];
const institution = { id: 1, name: "测试体检中心", branch_name: "中心分院" };
const packageItem = { id: 11, name: "基础套餐", price: 399 };

function mountView() {
  const wrapper = mount(ExamRegistrationView, {
    attachTo: document.body,
    global: { plugins: [ElementPlus] },
  });
  wrappers.push(wrapper);
  return wrapper;
}

beforeEach(() => {
  routeState.query = {};
  Object.values(api).forEach((mock) => mock.mockReset());
  api.fetchInstitutions.mockResolvedValue({ data: { items: [institution] } });
  api.fetchInstitutionPackages.mockResolvedValue({ data: { items: [packageItem] } });
  api.fetchRegistrations.mockResolvedValue({ data: { items: [] } });
  api.createRegistration.mockResolvedValue({ data: { match_result: "not_found" } });
  api.cancelRegistration.mockResolvedValue({ data: {} });
});

afterEach(() => {
  wrappers.splice(0).forEach((wrapper) => wrapper.unmount());
  document.body.innerHTML = "";
});

describe("ExamRegistrationView", () => {
  it("loads the direct registration form and existing registrations", async () => {
    const wrapper = mountView();
    await flushPromises();

    expect(api.fetchInstitutions).toHaveBeenCalledOnce();
    expect(api.fetchRegistrations).toHaveBeenCalledOnce();
    expect(wrapper.text()).toContain("新增体检登记");
    expect(wrapper.findAllComponents({ name: "ElSelect" })).toHaveLength(2);
    expect(wrapper.text()).toContain("机构未匹配的体检数据只保留 60 天");
  });

  it("loads packages after institution selection and submits all three fields", async () => {
    const wrapper = mountView();
    await flushPromises();

    const selects = wrapper.findAllComponents({ name: "ElSelect" });
    selects[0].vm.$emit("update:modelValue", institution.id);
    selects[0].vm.$emit("change", institution.id);
    await flushPromises();
    expect(api.fetchInstitutionPackages).toHaveBeenCalledWith(institution.id);

    selects[1].vm.$emit("update:modelValue", packageItem.id);
    await wrapper.get("form.registration-form").trigger("submit");
    await flushPromises();

    expect(api.createRegistration).toHaveBeenCalledWith({
      institution_id: institution.id,
      package_id: packageItem.id,
      exam_date: [
        new Date().getFullYear(),
        String(new Date().getMonth() + 1).padStart(2, "0"),
        String(new Date().getDate()).padStart(2, "0"),
      ].join("-"),
    });
    expect(api.fetchRegistrations).toHaveBeenCalledTimes(2);
  });
});
