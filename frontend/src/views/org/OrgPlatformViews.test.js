import { flushPromises, mount } from "@vue/test-utils";
import ElementPlus from "element-plus";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const push=vi.fn(),replace=vi.fn();
vi.mock("vue-router",()=>({useRouter:()=>({push,replace}),useRoute:()=>({query:{},fullPath:"/org/reports"})}));
const orgApi=vi.hoisted(()=>({
  fetchOrgPackages:vi.fn(),createOrgPackage:vi.fn(),updateOrgPackage:vi.fn(),deactivateOrgPackage:vi.fn(),reactivateOrgPackage:vi.fn(),
  fetchOrgReports:vi.fn(),createOrgReport:vi.fn(),fetchOrgReport:vi.fn(),addOrgReportIndicator:vi.fn(),deleteOrgReportIndicator:vi.fn(),addOrgTextResult:vi.fn(),deleteOrgTextResult:vi.fn(),uploadOrgHealthAsset:vi.fn(),deleteOrgHealthAsset:vi.fn(),lockOrgReport:vi.fn(),submitOrgReport:vi.fn(),uploadOrgReportOcr:vi.fn(),
  fetchOrgAppointments:vi.fn(),attendOrgAppointment:vi.fn(),invalidateOrgAppointment:vi.fn(),fetchOrgAppointmentCapacity:vi.fn(),updateOrgAppointmentCapacity:vi.fn(),
}));
const healthApi=vi.hoisted(()=>({fetchHealthDomains:vi.fn()}));
const indicatorApi=vi.hoisted(()=>({fetchIndicatorDicts:vi.fn()}));
const dashboardApi=vi.hoisted(()=>({fetchOrgDashboard:vi.fn()}));
vi.mock("../../api/org",()=>orgApi);vi.mock("../../api/health",()=>healthApi);vi.mock("../../api/indicators",()=>indicatorApi);vi.mock("../../api/dashboards",()=>dashboardApi);

import OrgDashboardView from "./OrgDashboardView.vue";
import OrgPackagesView from "./OrgPackagesView.vue";
import OrgReportsView from "./OrgReportsView.vue";

const wrappers=[];
const mountView=(component)=>{const wrapper=mount(component,{attachTo:document.body,global:{plugins:[ElementPlus],stubs:{teleport:true}}});wrappers.push(wrapper);return wrapper;};

beforeEach(()=>{
  vi.clearAllMocks();
  healthApi.fetchHealthDomains.mockResolvedValue({data:{items:[{id:1,name:"心脑血管"},{id:2,name:"代谢"}]}});
  indicatorApi.fetchIndicatorDicts.mockResolvedValue({data:{items:[]}});
  orgApi.fetchOrgAppointmentCapacity.mockResolvedValue({data:{unlimited:false,daily_appointment_limit:20}});
  orgApi.fetchOrgReports.mockResolvedValue({data:{items:[]}});
  orgApi.fetchOrgAppointments.mockResolvedValue({data:{items:[]}});
});
afterEach(()=>{wrappers.splice(0).forEach((wrapper)=>wrapper.unmount());document.body.innerHTML="";});

describe("institution platform views",()=>{
  it("turns dashboard counts into actionable daily work",async()=>{
    dashboardApi.fetchOrgDashboard.mockResolvedValue({data:{summary:{institution:{name:"澄心健康管理中心"},today:{booked:8,capacity:20,remaining:12,awaiting_arrival:3,awaiting_archive:2,waitlist_subscriptions:1},active_package_count:3,pending_package_review_count:1,recent_package_reviews:[]}}});
    const wrapper=mountView(OrgDashboardView);await flushPromises();
    expect(wrapper.text()).toContain("今日运营工作台");expect(wrapper.text()).toContain("等待到检");expect(wrapper.text()).toContain("完成待归档数据");
    await wrapper.get(".org-task").trigger("click");expect(push).toHaveBeenCalledWith({name:"org-reports",query:{view:"today"}});
  });

  it("renders user-facing service cards and a three-step design wizard",async()=>{
    orgApi.fetchOrgPackages.mockResolvedValue({data:{items:[{id:1,name:"慢病风险综合评估",focus_area:"长期风险管理",gender_scope:"all",price:1299,is_active:true,package_type:"combined",audience:"关注慢病风险的成年人",description:"提供综合健康评估",booking_notice:"检查前请空腹",domains:[{id:1,name:"心脑血管"},{id:2,name:"代谢"}],pending_request:null}]}});
    const wrapper=mountView(OrgPackagesView);await flushPromises();
    const card=wrapper.get(".package-card");expect(card.text()).toContain("组合服务");expect(card.text()).toContain("关注慢病风险的成年人");expect(card.text()).not.toContain("female_all");
    await wrapper.get(".package-hero .el-button").trigger("click");await flushPromises();expect(wrapper.vm.dialogVisible).toBe(true);expect(wrapper.vm.step).toBe(0);
  });

  it("organizes appointments by real service tasks and removes OCR jargon",async()=>{
    orgApi.fetchOrgAppointments.mockResolvedValue({data:{items:[{id:8,appointment_date:new Date().toISOString().slice(0,10),status:"awaiting_report",package_name:"都市年度基础体检",user:{name:"张明",health_id:"HD-001"},report_id:null,report_status:null}]}});
    const wrapper=mountView(OrgReportsView);await flushPromises();
    expect(wrapper.text()).toContain("今日接待");expect(wrapper.text()).toContain("待归档");expect(wrapper.text()).toContain("历史健康数据");
    const archiveTab=wrapper.findAll(".report-tabs button").find((item)=>item.text().includes("待归档"));await archiveTab.trigger("click");await flushPromises();
    expect(wrapper.text()).toContain("都市年度基础体检");expect(wrapper.text()).toContain("导入体检报告并识别");expect(wrapper.text()).not.toContain("OCR 上传");
  });
});
