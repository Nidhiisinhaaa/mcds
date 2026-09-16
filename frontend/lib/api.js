// Thin fetch wrapper for the Django backend: JWT storage, auto-refresh on
// 401, and one small helper per endpoint the patient-side UI needs.

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const ACCESS_KEY = "bedside_access";
const REFRESH_KEY = "bedside_refresh";

export function getTokens() {
  if (typeof window === "undefined") return { access: null, refresh: null };
  return {
    access: window.localStorage.getItem(ACCESS_KEY),
    refresh: window.localStorage.getItem(REFRESH_KEY),
  };
}

export function setTokens({ access, refresh }) {
  if (typeof window === "undefined") return;
  if (access) window.localStorage.setItem(ACCESS_KEY, access);
  if (refresh) window.localStorage.setItem(REFRESH_KEY, refresh);
}

export function clearTokens() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(ACCESS_KEY);
  window.localStorage.removeItem(REFRESH_KEY);
}

export function isAuthenticated() {
  return Boolean(getTokens().access);
}

/** doctor -> /doctor, patient -> /patient (used right after login). */
export function redirectPathForRole(role) {
  return role === "doctor" ? "/doctor" : "/patient";
}

async function refreshAccessToken() {
  const { refresh } = getTokens();
  if (!refresh) return false;
  try {
    const res = await fetch(`${API_URL}/api/auth/refresh/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh }),
    });
    if (!res.ok) return false;
    const data = await res.json();
    setTokens({ access: data.access });
    return true;
  } catch {
    return false;
  }
}

/**
 * Low-level request helper. Returns { ok, status, data }. On a 401 it tries
 * one silent refresh-and-retry before giving up and clearing tokens.
 */
export async function apiFetch(path, { method = "GET", body, headers = {}, auth = true, retry = true } = {}) {
  const isForm = typeof FormData !== "undefined" && body instanceof FormData;
  const finalHeaders = { ...headers };
  if (!isForm && body !== undefined) {
    finalHeaders["Content-Type"] = "application/json";
  }
  if (auth) {
    const { access } = getTokens();
    if (access) finalHeaders["Authorization"] = `Bearer ${access}`;
  }

  let res;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method,
      headers: finalHeaders,
      body: isForm ? body : body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    return { ok: false, status: 0, data: { detail: "Network error - is the server reachable?" } };
  }

  if (res.status === 401 && auth && retry) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      return apiFetch(path, { method, body, headers, auth, retry: false });
    }
    clearTokens();
    if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
      window.location.href = "/login";
    }
  }

  let data = null;
  try {
    data = await res.json();
  } catch {
    data = null;
  }
  return { ok: res.ok, status: res.status, data };
}

// ---- Auth ---------------------------------------------------------------

export function register({ username, email, password, full_name, preferred_language }) {
  return apiFetch("/api/auth/register/", {
    method: "POST",
    auth: false,
    body: { username, email, password, full_name, preferred_language },
  });
}

export async function login({ username, password }) {
  const result = await apiFetch("/api/auth/login/", {
    method: "POST",
    auth: false,
    body: { username, password },
  });
  if (result.ok) {
    setTokens({ access: result.data.access, refresh: result.data.refresh });
  }
  return result;
}

export function logout() {
  clearTokens();
}

export function getMe() {
  return apiFetch("/api/auth/me/");
}

export function patchMe(payload) {
  return apiFetch("/api/auth/me/", { method: "PATCH", body: payload });
}

export function postConsent() {
  return apiFetch("/api/auth/consent/", { method: "POST" });
}

// ---- Consultations --------------------------------------------------------

export function listConsultations() {
  return apiFetch("/api/consultations/");
}

export function createConsultation(language) {
  return apiFetch("/api/consultations/", {
    method: "POST",
    body: language ? { language } : {},
  });
}

export function getConsultation(id) {
  return apiFetch(`/api/consultations/${id}/`);
}

export function getConsultationState(id) {
  return apiFetch(`/api/consultations/${id}/state/`);
}

export function postConsultationText(id, text) {
  return apiFetch(`/api/consultations/${id}/text/`, {
    method: "POST",
    body: { text },
  });
}

export function postConsultationAudio(id, blob, filename) {
  const form = new FormData();
  form.append("audio", blob, filename);
  return apiFetch(`/api/consultations/${id}/audio/`, {
    method: "POST",
    body: form,
  });
}

/** Fetches the PDF as a blob and triggers a browser download - the JWT has
 * to go in an Authorization header, so a plain <a href> won't work. */
export async function downloadConsultationReport(id) {
  const { access } = getTokens();
  const res = await fetch(`${API_URL}/api/consultations/${id}/report.pdf`, {
    headers: access ? { Authorization: `Bearer ${access}` } : {},
  });
  if (!res.ok) {
    throw new Error("Could not download the report.");
  }
  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `consultation-${id}-report.pdf`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

// ---- Doctor ---------------------------------------------------------------

export function listDoctorConsultations({ status: statusFilter, q } = {}) {
  const params = new URLSearchParams();
  if (statusFilter) params.set("status", statusFilter);
  if (q) params.set("q", q);
  const query = params.toString();
  return apiFetch(`/api/doctor/consultations/${query ? `?${query}` : ""}`);
}

export function getDoctorConsultation(id) {
  return apiFetch(`/api/doctor/consultations/${id}/`);
}

export function patchDoctorLifestyle(id, overrides) {
  return apiFetch(`/api/doctor/consultations/${id}/lifestyle/`, {
    method: "PATCH",
    body: { doctor_overrides: overrides },
  });
}

export function postDoctorNote(id, text) {
  return apiFetch(`/api/doctor/consultations/${id}/notes/`, {
    method: "POST",
    body: { text },
  });
}

export function postDoctorReview(id) {
  return apiFetch(`/api/doctor/consultations/${id}/review/`, { method: "POST" });
}

// ---- Doctor-led consultations ---------------------------------------------

export function searchDoctorPatients(q) {
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  const query = params.toString();
  return apiFetch(`/api/doctor/patients/${query ? `?${query}` : ""}`);
}

export function createDoctorPatient(payload) {
  return apiFetch("/api/doctor/patients/", { method: "POST", body: payload });
}

export function createDoctorConsultation({ patientId, language }) {
  return apiFetch("/api/doctor/consultations/", {
    method: "POST",
    body: language ? { patient_id: patientId, language } : { patient_id: patientId },
  });
}

export function postDoctorConsentConfirm(id) {
  return apiFetch(`/api/doctor/consultations/${id}/consent/`, { method: "POST" });
}

// The doctor-led recording session reuses the same message-posting and
// state endpoints the patient's own chat uses (see
// consultations.views._get_accessible_consultation on the backend) -
// getConsultationState/postConsultationText/postConsultationAudio above are
// shared, not duplicated, for that reason.

export { API_URL };
