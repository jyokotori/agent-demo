const rawBaseUrl = import.meta.env.VITE_API_BASE_URL ?? '';
const normalizedBaseUrl = rawBaseUrl.endsWith('/') ? rawBaseUrl.slice(0, -1) : rawBaseUrl;

export const API_BASE_URL = normalizedBaseUrl;

export const API_ENDPOINTS = {
  chatStream: `${API_BASE_URL}/api/agent/chat/stream`,
  reservationDecision: `${API_BASE_URL}/api/agent/reservations/decision`
} as const;

export const DEFAULT_HEADERS: HeadersInit = {
  'Content-Type': 'application/json'
};
