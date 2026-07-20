import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";

import MeasurementDrawer from "./MeasurementDrawer.vue";

vi.mock("../api/indicators", () => ({ fetchIndicatorDicts: vi.fn() }));
vi.mock("../api/health", () => ({
  createMeasurement: vi.fn(),
  deleteMeasurement: vi.fn(),
  fetchMeasurements: vi.fn(),
  updateMeasurement: vi.fn(),
}));

const DrawerStub = {
  props: ["modelValue", "title"],
  emits: ["update:modelValue", "open", "closed"],
  template: "<section><h1>{{ title }}</h1><slot /></section>",
};
const SlotStub = { template: "<div><slot /></div>" };

describe("MeasurementDrawer", () => {
  it("presents daily measurement as a guided action instead of a data table", () => {
    const wrapper = mount(MeasurementDrawer, {
      props: { modelValue: true },
      global: {
        stubs: {
          ElDrawer: DrawerStub,
          ElAlert: true,
          ElForm: SlotStub,
          ElFormItem: SlotStub,
          ElSelect: SlotStub,
          ElOption: true,
          ElInputNumber: true,
          ElDatePicker: true,
          ElButton: SlotStub,
          ElEmpty: true,
        },
      },
    });

    expect(wrapper.text()).toContain("记录今日测量");
    expect(wrapper.text()).toContain("花一分钟，记下此刻的身体状态");
    expect(wrapper.find("table").exists()).toBe(false);
  });
});
