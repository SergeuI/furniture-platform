function getSpeechSynthesis() {
  if (typeof window === 'undefined') {
    return null;
  }

  return window.speechSynthesis || null;
}

export function isBrowserSpeechSynthesisSupported() {
  return Boolean(getSpeechSynthesis() && typeof window.SpeechSynthesisUtterance === 'function');
}

export function speakBrowserText(text, { onEnd, onError } = {}) {
  const synthesis = getSpeechSynthesis();

  if (!synthesis || typeof window.SpeechSynthesisUtterance !== 'function') {
    return false;
  }

  const value = String(text || '').trim();

  if (!value) {
    return false;
  }

  const utterance = new window.SpeechSynthesisUtterance(value);
  utterance.lang = 'uk-UA';

  utterance.onend = () => {
    if (typeof onEnd === 'function') {
      onEnd();
    }
  };

  utterance.onerror = (event) => {
    if (typeof onError === 'function') {
      onError(event.error || 'unknown_error');
    }
  };

  synthesis.cancel();
  synthesis.speak(utterance);
  return true;
}
