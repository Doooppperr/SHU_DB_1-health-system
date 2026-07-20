import http from "./http";

export const fetchAppointmentAvailability = (appointmentDate) => http.get("/appointments/availability", { params: { appointment_date: appointmentDate } });
export const fetchMyAppointments = () => http.get("/appointments");
export const createAppointment = (payload) => http.post("/appointments", payload);
export const cancelAppointment = (id) => http.post(`/appointments/${id}/cancel`);
export const fetchBookingGroups = () => http.get("/booking-groups");
export const createBookingGroup = (payload) => http.post("/booking-groups", payload);
export const cancelBookingGroup = (id) => http.post(`/booking-groups/${id}/cancel`);
export const fetchWaitlistSubscriptions = () => http.get("/waitlist-subscriptions");
export const createWaitlistSubscription = (payload) => http.post("/waitlist-subscriptions", payload);
export const cancelWaitlistSubscription = (id) => http.delete(`/waitlist-subscriptions/${id}`);
