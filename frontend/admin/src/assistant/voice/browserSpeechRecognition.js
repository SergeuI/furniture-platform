function getSpeechRecognitionConstructor() {
  if (typeof window === 'undefined') {
    return null;
  }

  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
}

export function isBrowserSpeechRecognitionSupported() {
  return Boolean(getSpeechRecognitionConstructor());
}

export function createBrowserSpeechRecognition({ onResult, onError, onEnd } = {}) {
  const SpeechRecognition = getSpeechRecognitionConstructor();

  if (!SpeechRecognition) {
    return null;
  }

  const recognition = new SpeechRecognition();
  recognition.lang = 'uk-UA';
  recognition.continuous = false;
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;

  recognition.onresult = (event) => {
    const transcript = event.results?.[0]?.[0]?.transcript?.trim() || '';
    if (transcript && typeof onResult === 'function') {
      onResult(transcript);
    }
  };

  recognition.onerror = (event) => {
    if (typeof onError === 'function') {
      onError(event.error || 'unknown_error');
    }
  };

  recognition.onend = () => {
    if (typeof onEnd === 'function') {
      onEnd();
    }
  };

  return recognition;
}
