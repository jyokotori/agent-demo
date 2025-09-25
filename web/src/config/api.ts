export const API_BASE_URL = 'http://127.0.0.1:8000';

export const API_ENDPOINTS = {
  chatStream: `${API_BASE_URL}/api/agent/chat/stream`,
  reservationDecision: `${API_BASE_URL}/api/agent/reservations/decision`
} as const;

export const DEFAULT_HEADERS: HeadersInit = {
  'Content-Type': 'application/json'
};
