import { API_BASE_URL } from '../../api.js';

const TOKEN_STORAGE_KEY = 'furniture_admin_token';

export async function captureUnknownPhrase(phrase) {
  const value = String(phrase || '').trim();

  if (!value) {
    return null;
  }

  const token = typeof window !== 'undefined'
    ? window.localStorage.getItem(TOKEN_STORAGE_KEY) || ''
    : '';

  if (!token) {
    return null;
  }

  const response = await fetch(`${API_BASE_URL}/assistant/unknown-phrases`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ phrase: value }),
  });

  if (!response.ok) {
    throw new Error(`Assistant phrase capture failed (HTTP ${response.status})`);
  }

  return response.json();
}
