import http from "./http";

export const fetchAppointmentAvailability = (appointmentDate) => http.get("/appointments/availability", { params: { appointment_date: appointmentDate } });
export const fetchMyAppointments = () => http.get("/appointments");
export const createAppointment = (payload) => http.post("/appointments", payload);
export const cancelAppointment = (id) => http.post(`/appointments/${id}/cancel`);
