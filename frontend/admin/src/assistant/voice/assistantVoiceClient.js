import { API_BASE_URL } from '../../api.js';

const TOKEN_STORAGE_KEY = 'furniture_admin_token';

export async function fetchAssistantVoice(text, voiceProfile = 'male') {
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
    body: JSON.stringify({ text: value, voice_profile: voiceProfile }),
  });

  console.debug('[assistant audio] status:', response.status);
  console.debug('[assistant audio] cache:', response.headers.get('X-MPFC-Voice-Cache') || 'unknown');

  if (!response.ok) {
    throw new Error(`Assistant voice request failed (HTTP ${response.status})`);
  }

  const blob = await response.blob();
  console.debug('[assistant audio] blob size:', blob.size, 'content type:', blob.type);

  if (!blob.size) {
    throw new Error('Assistant voice returned empty audio');
  }

  return blob;
}
