import { API_BASE_URL } from '../../api.js';

const TOKEN_STORAGE_KEY = 'furniture_admin_token';

function getAssistantAuthToken() {
  return typeof window !== 'undefined'
    ? window.localStorage.getItem(TOKEN_STORAGE_KEY) || ''
    : '';
}

export async function captureUnknownPhrase(phrase) {
  const value = String(phrase || '').trim();

  if (!value) {
    return null;
  }

  const token = getAssistantAuthToken();

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

export async function listUnknownPhrases(status = 'new') {
  const token = getAssistantAuthToken();

  if (!token) {
    throw new Error('Authentication is required');
  }

  const params = new URLSearchParams();
  if (status) {
    params.set('status', status);
  }

  const suffix = params.toString() ? `?${params.toString()}` : '';
  const response = await fetch(`${API_BASE_URL}/assistant/unknown-phrases${suffix}`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new Error(`Assistant phrase list failed (HTTP ${response.status})`);
  }

  return response.json();
}

export async function mapUnknownPhrase(phraseId, actionId) {
  const token = getAssistantAuthToken();
  const id = String(phraseId || '').trim();
  const action = String(actionId || '').trim();

  if (!token) {
    throw new Error('Authentication is required');
  }
  if (!id || !action) {
    throw new Error('Phrase and action are required');
  }

  const response = await fetch(`${API_BASE_URL}/assistant/unknown-phrases/${encodeURIComponent(id)}/map`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ action_id: action }),
  });

  if (!response.ok) {
    throw new Error(`Assistant phrase mapping failed (HTTP ${response.status})`);
  }

  return response.json();
}


export async function fetchPhraseMappings() {
  const token = getAssistantAuthToken();

  if (!token) {
    return [];
  }

  const response = await fetch(`${API_BASE_URL}/assistant/phrase-mappings`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new Error(`Assistant phrase mappings failed (HTTP ${response.status})`);
  }

  const payload = await response.json();
  return Array.isArray(payload?.items) ? payload.items : [];
}
