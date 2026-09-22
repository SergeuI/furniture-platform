import { API_BASE_URL } from '../../api.js';

const TOKEN_STORAGE_KEY = 'furniture_admin_token';

export async function fetchAssistantVoice(text) {
  const value = String(text || '').trim();

  if (!value) {
    throw new Error('Voice text is required');
  }

  const token = typeof window !== 'undefined'
    ? window.localStorage.getItem(TOKEN_STORAGE_KEY) || ''
    : '';

  if (!token) {
    throw new Error('Authentication is required');
  }

  const response = await fetch(`${API_BASE_URL}/assistant/voice`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ text: value }),
  });

  if (!response.ok) {
    throw new Error(`Assistant voice request failed (HTTP ${response.status})`);
  }

  const blob = await response.blob();

  if (!blob.size) {
    throw new Error('Assistant voice returned empty audio');
  }

  return blob;
}
