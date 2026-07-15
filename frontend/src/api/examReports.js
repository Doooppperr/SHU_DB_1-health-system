import http from "./http";

export const fetchExamReports = () => http.get("/exam-reports");
export const fetchExamReport = (id) => http.get(`/exam-reports/${id}`);
