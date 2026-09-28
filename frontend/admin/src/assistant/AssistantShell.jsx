import React, { useEffect, useRef, useState } from 'react';
import './AssistantShell.css';
import { executeAssistantAction } from './actions/actionRegistry.js';
import { resolveAssistantCommand, setAssistantPhraseMappings } from './commands/commandResolver.js';
import { captureUnknownPhrase, fetchPhraseMappings } from './phrases/assistantPhraseClient.js';
import { getAssistantResponse } from './responses/responseRegistry.js';
import { ASSISTANT_STATES } from './state/assistantState.js';
import { createBrowserSpeechRecognition, isBrowserSpeechRecognitionSupported } from './voice/browserSpeechRecognition.js';
import { fetchAssistantVoice } from './voice/assistantVoiceClient.js';
import assistantIdleImage from './avatar/states/assistant_idle.png';
import assistantListeningImage from './avatar/states/assistant_listening.png';
import assistantProcessingImage from './avatar/states/assistant_processing.png';
import assistantSpeakingImage from './avatar/states/assistant_speaking.png';
import assistantSuccessImage from './avatar/states/assistant_success.png';

const ASSISTANT_STATE_IMAGES = Object.freeze({
  idle: assistantIdleImage,
  listening: assistantListeningImage,
  processing: assistantProcessingImage,
  executing: assistantProcessingImage,
  speaking: assistantSpeakingImage,
  success: assistantSuccessImage,
  error: assistantIdleImage,
});

const WAKE_WORD_VARIANTS = ['асистент', 'ассистент', 'assistant'];
function normalizeWakeWordTranscript(value) {
  const normalized = String(value || '').trim().toLowerCase().replace(/^[,!.?\s]+|[,!.?\s]+$/g, '');
  const match = WAKE_WORD_VARIANTS.find((word) => normalized === word || normalized.startsWith(`${word} `) || normalized.startsWith(`${word},`) || normalized.startsWith(`${word}!`));
  return { normalized, matched: Boolean(match), command: match ? normalized.slice(match.length).replace(/^[,!.?\s]+/, '').trim() : '' };
}

export default function AssistantShell() {
  const [isOpen, setIsOpen] = useState(false);
  const [commandText, setCommandText] = useState('');
  const [commandResult, setCommandResult] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [voiceSessionActive, setVoiceSessionActive] = useState(false);
  const [awaitingVoiceCommand, setAwaitingVoiceCommand] = useState(false);
  const [voiceDiagnostics, setVoiceDiagnostics] = useState({ mic: 'off', raw: '', wake: 'not matched', command: '', action: 'none' });
  const [audioDiagnostics, setAudioDiagnostics] = useState({ status: 'idle', error: '' });
  const [assistantState, setAssistantState] = useState(ASSISTANT_STATES.IDLE);
  const [isTextMode, setIsTextMode] = useState(false);
  const greetingAudioUrlRef = useRef(null);
  const greetingAudioPromiseRef = useRef(null);
  const audioRef = useRef(null);
  const recognitionRef = useRef(null);
  const voiceSessionRef = useRef(false);
  const isOpenRef = useRef(false);
  const voiceSessionActiveRef = useRef(false);
  const isSpeakingRef = useRef(false);
  const mountedRef = useRef(true);
  const recognitionRunningRef = useRef(false);
  const hasFinalTranscriptRef = useRef(false);
  const assistantImage = ASSISTANT_STATE_IMAGES[assistantState] || ASSISTANT_STATE_IMAGES.idle;
  const greeting = 'Привіт! Я MPFC Assistant. Чим можу допомогти?';
  useEffect(() => { isOpenRef.current = isOpen; }, [isOpen]);
  useEffect(() => {
    mountedRef.current = true;

    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    greetingAudioPromiseRef.current = fetchAssistantVoice(greeting, 'male')
      .then((blob) => {
        greetingAudioUrlRef.current = URL.createObjectURL(blob);
      })
      .catch((error) => {
        console.warn('MPFC Assistant greeting preload failed:', error);
      });

    return () => {
      if (greetingAudioUrlRef.current) {
        URL.revokeObjectURL(greetingAudioUrlRef.current);
        greetingAudioUrlRef.current = null;
      }
    };
  }, []);

  function handleOpenAssistant() {
    setIsOpen(true);
    setCommandResult(greeting);
    void playGreeting();
  }

  async function playGreeting() {
    try {
      if (greetingAudioPromiseRef.current) {
        await greetingAudioPromiseRef.current;
      }
      if (!greetingAudioUrlRef.current) {
        const blob = await fetchAssistantVoice(greeting, 'male');
        greetingAudioUrlRef.current = URL.createObjectURL(blob);
      }
      const audio = new Audio(greetingAudioUrlRef.current);
      audioRef.current?.pause();
      audioRef.current = audio;
      audio.addEventListener('ended', () => { isSpeakingRef.current = false; setAssistantState(ASSISTANT_STATES.IDLE); if (voiceSessionActiveRef.current && recognitionRef.current) { try { recognitionRunningRef.current = true; recognitionRef.current.start(); } catch { recognitionRunningRef.current = false; } } }, { once: true });
      setAssistantState(ASSISTANT_STATES.SPEAKING);
      isSpeakingRef.current = true;
      recognitionRef.current?.abort();
      setAudioDiagnostics({ status: 'playing', error: '' });
      await audio.play();
    } catch (error) {
      console.warn('MPFC Assistant greeting playback failed:', error);
      setAudioDiagnostics({ status: 'error', error: `${error?.name || 'Error'}: ${error?.message || error}` });
      setAssistantState(ASSISTANT_STATES.ERROR);
      if (voiceSessionActiveRef.current && mountedRef.current && isOpenRef.current) {
        window.setTimeout(() => {
          if (!recognitionRunningRef.current && voiceSessionActiveRef.current && mountedRef.current && !isSpeakingRef.current) {
            try { recognitionRunningRef.current = true; setIsListening(true); recognitionRef.current?.start(); } catch { recognitionRunningRef.current = false; }
          }
        }, 150);
      }
    }
  }

  useEffect(() => {
    if (!isOpen) {
      return undefined;
    }

    let cancelled = false;

    void fetchPhraseMappings()
      .then((items) => {
        if (!cancelled) {
          setAssistantPhraseMappings(items);
        }
      })
      .catch(() => {});

    return () => {
      cancelled = true;
    };
  }, [isOpen]);

  function handleVoiceInput() {
    setIsTextMode(false);
    if (!isBrowserSpeechRecognitionSupported()) {
      setAssistantState(ASSISTANT_STATES.ERROR);
      setCommandResult('Voice recognition is not supported in this browser.');
      return;
    }

    let recognitionFailed = false;
    let commandStarted = false;
    const restartRecognition = () => {
      const state = {
        session: voiceSessionActiveRef.current,
        running: recognitionRunningRef.current,
        speaking: isSpeakingRef.current,
        open: isOpenRef.current,
        mounted: mountedRef.current,
      };
      console.debug('[MPFC VOICE] RESTART_REQUEST', state);
      if (!voiceSessionActiveRef.current || !mountedRef.current || !isOpenRef.current || isSpeakingRef.current || recognitionRunningRef.current) {
        console.debug('[MPFC VOICE] RESTART_BLOCKED', state);
        return;
      }
      console.debug('[MPFC VOICE] RESTART_ALLOWED', state);
      window.setTimeout(() => {
        const delayedState = {
          session: voiceSessionActiveRef.current,
          running: recognitionRunningRef.current,
          speaking: isSpeakingRef.current,
          open: isOpenRef.current,
          mounted: mountedRef.current,
        };
        if (!voiceSessionActiveRef.current || !mountedRef.current || !isOpenRef.current || isSpeakingRef.current || recognitionRunningRef.current) {
          console.debug('[MPFC VOICE] RESTART_BLOCKED', delayedState);
          return;
        }
        try {
          recognitionRunningRef.current = true;
          setIsListening(true);
          setVoiceDiagnostics((value) => ({ ...value, mic: 'listening' }));
          recognition.start();
        } catch {
          recognitionRunningRef.current = false;
        }
      }, 150);
    };
    setVoiceDiagnostics((value) => ({ ...value, mic: 'starting' }));
    console.debug('[MPFC VOICE] MIC_CLICK');
    const recognition = createBrowserSpeechRecognition({
      onResult: (transcript) => {
        if (commandStarted) return;
        commandStarted = true;
        hasFinalTranscriptRef.current = true;
        const { normalized, matched, command } = normalizeWakeWordTranscript(transcript);
        console.debug('[MPFC VOICE] RECOGNITION_RESULT', { transcript });
        setVoiceDiagnostics((value) => ({ ...value, raw: transcript, wake: matched || awaitingVoiceCommand ? 'matched' : 'not matched' }));
        if (!awaitingVoiceCommand && !matched) {
          setVoiceDiagnostics((value) => ({ ...value, command: '', action: 'none' }));
          commandStarted = false;
          return;
        }
        const effectiveCommand = awaitingVoiceCommand ? normalized : command;
        setIsListening(false);
        if (!effectiveCommand) { setAwaitingVoiceCommand(true); setAssistantState(ASSISTANT_STATES.LISTENING); setCommandResult('Слухаю.'); return; }
        setAwaitingVoiceCommand(false);
        setCommandText(effectiveCommand);
        setVoiceDiagnostics((value) => ({ ...value, command: effectiveCommand }));
        void processAssistantCommand(effectiveCommand, { interactionMode: 'voice' });
        commandStarted = false;
      },
      onError: (errorCode = 'unknown_error') => {
        console.debug('[MPFC VOICE] RECOGNITION_ERROR', errorCode);
        if (['no-speech', 'aborted', 'network'].includes(errorCode)) {
          recognitionFailed = false;
          return;
        }
        recognitionFailed = true;
        setAssistantState(ASSISTANT_STATES.ERROR);
        setCommandResult('Не вдалося розпізнати голос. Спробуйте ще раз.');
        setVoiceDiagnostics((value) => ({ ...value, mic: 'error' }));
      },
      onEnd: () => {
        recognitionRunningRef.current = false;
        setIsListening(false);
        setVoiceDiagnostics((value) => ({ ...value, mic: 'ended' }));
        console.debug('[MPFC VOICE] RECOGNITION_END', {
          session: voiceSessionActiveRef.current,
          running: recognitionRunningRef.current,
          speaking: isSpeakingRef.current,
          open: isOpenRef.current,
          mounted: mountedRef.current,
        });
        if (voiceSessionActiveRef.current && mountedRef.current && isOpenRef.current && !isSpeakingRef.current) {
          setAssistantState(ASSISTANT_STATES.IDLE);
          restartRecognition();
        }
      },
    });

    if (!recognition) {
      return;
    }

    setIsListening(true);
    setVoiceDiagnostics((value) => ({ ...value, mic: 'listening' }));
    setVoiceSessionActive(true);
    voiceSessionActiveRef.current = true;
    voiceSessionRef.current = true;
    recognitionRef.current = recognition;
    setAssistantState(ASSISTANT_STATES.LISTENING);
    setCommandResult('Слухаю...');

    try {
      recognitionRunningRef.current = true;
      recognition.start();
    } catch {
      recognitionRunningRef.current = false;
      setIsListening(false);
      setAssistantState(ASSISTANT_STATES.ERROR);
      setCommandResult('Не вдалося увімкнути мікрофон. Спробуйте ще раз.');
    }
  }

  async function speakAssistantResponse(text, finalState = ASSISTANT_STATES.SUCCESS) {
    let audioUrl = null;

    try {
      const blob = await fetchAssistantVoice(text, 'male');
      audioUrl = URL.createObjectURL(blob);
      const audio = audioRef.current || new Audio();
      audio.pause();
      audio.src = audioUrl;
      audioRef.current = audio;
      audio.addEventListener('ended', () => { URL.revokeObjectURL(audioUrl); isSpeakingRef.current = false; setAssistantState(finalState); if (voiceSessionActiveRef.current && recognitionRef.current) { try { recognitionRunningRef.current = true; recognitionRef.current.start(); } catch { recognitionRunningRef.current = false; } } }, { once: true });
      audio.addEventListener('error', () => URL.revokeObjectURL(audioUrl), { once: true });
      setAssistantState(ASSISTANT_STATES.SPEAKING);
      isSpeakingRef.current = true;
      recognitionRef.current?.abort();
      setAudioDiagnostics({ status: 'playing', error: '' });
      await audio.play();
      console.debug('[assistant audio] started');
      return;
    } catch (error) {
      setAudioDiagnostics({ status: 'error', error: `${error?.name || 'Error'}: ${error?.message || error}` });
      isSpeakingRef.current = false;
      if (audioUrl) {
        URL.revokeObjectURL(audioUrl);
      }

      setAssistantState(ASSISTANT_STATES.ERROR);
      if (voiceSessionActiveRef.current && mountedRef.current && isOpenRef.current) {
        window.setTimeout(() => {
          if (!recognitionRunningRef.current && voiceSessionActiveRef.current && mountedRef.current && !isSpeakingRef.current) {
            try { recognitionRunningRef.current = true; setIsListening(true); recognitionRef.current?.start(); } catch { recognitionRunningRef.current = false; }
          }
        }, 150);
      }
    }
  }

  function stopVoiceSession() {
    voiceSessionRef.current = false;
    voiceSessionActiveRef.current = false;
    setVoiceSessionActive(false);
    setAwaitingVoiceCommand(false);
    setIsListening(false);
    recognitionRef.current?.abort();
    recognitionRunningRef.current = false;
  }

  async function processAssistantCommand(text, { interactionMode = 'text' } = {}) {
    const isVoiceInteraction = interactionMode === 'voice';
    setAssistantState(ASSISTANT_STATES.PROCESSING);
    const resolved = resolveAssistantCommand(text);

    if (!resolved.success) {
      const responseText = getAssistantResponse(resolved.reason === 'empty_command' ? 'assistant.command.empty' : 'assistant.command.unknown');
      setAssistantState(resolved.reason === 'empty_command' ? ASSISTANT_STATES.IDLE : ASSISTANT_STATES.ERROR);
      setCommandResult(responseText);
      if (resolved.reason === 'unknown_command') {
        void captureUnknownPhrase(text).catch(() => {});
        if (isVoiceInteraction) void speakAssistantResponse(responseText, ASSISTANT_STATES.ERROR);
      }
      return;
    }

    setAssistantState(ASSISTANT_STATES.EXECUTING);
    const executed = executeAssistantAction(resolved.actionId);
    setVoiceDiagnostics((value) => ({ ...value, action: resolved.actionId }));
    console.debug('[assistant voice] action:', resolved.actionId);
    setAssistantState(executed.success ? ASSISTANT_STATES.SUCCESS : ASSISTANT_STATES.ERROR);
    const resultText = getAssistantResponse(executed.success ? `assistant.action.${resolved.actionId}.success` : 'assistant.command.error');
    setCommandResult(resultText);
    if (executed.success && isVoiceInteraction) {
      void speakAssistantResponse(resultText);
    }
  }

  function handleCommandSubmit(event) {

    event.preventDefault();
    const submittedCommand = commandText;
    setCommandText('');
    void processAssistantCommand(submittedCommand, { interactionMode: 'text' });
  }

  return (
    <div className='mp-assistant'>
      <div className={`mp-assistant__floating${isOpen ? ' is-open' : ''}`}>
        {isOpen && <>
          <img className='mp-assistant__floating-character' src={assistantImage} alt='MP Assistant' />
          <button type='button' className='mp-assistant__close' onClick={() => { stopVoiceSession(); setIsOpen(false); }} aria-label='Закрити MPFC Assistant'>×</button>
          {commandResult && <div className='mp-assistant__bubble' role='status'>{commandResult}</div>}
          {isTextMode && <form className='mp-assistant__text-form' onSubmit={handleCommandSubmit}><input autoFocus type='text' value={commandText} onChange={(event) => setCommandText(event.target.value)} placeholder='Напишіть повідомлення...' aria-label='Напишіть повідомлення' /></form>}
          <div className='mp-assistant__floating-actions'>
            <button type='button' className='mp-assistant__action' onClick={() => setIsTextMode((value) => !value)} aria-label='Текстове повідомлення'>✎</button>
            <button type='button' className={`mp-assistant__action${voiceSessionActive ? ' is-active' : ''}`} onClick={handleVoiceInput} aria-label={voiceSessionActive ? 'Голосова сесія увімкнена' : 'Увімкнути мікрофон'}><svg viewBox='0 0 24 24' aria-hidden='true'><path d='M12 14a3 3 0 0 0 3-3V6a3 3 0 0 0-6 0v5a3 3 0 0 0 3 3Zm6-3a6 6 0 0 1-12 0m6 6v4m-3 0h6' /></svg></button>
          </div>
        </>}
        {!isOpen && <button type='button' className='mp-assistant__launcher' onClick={handleOpenAssistant} aria-label='Відкрити MP Assistant'><img className='mp-assistant__launcher-image' src={assistantIdleImage} alt='' /></button>}
      </div>
    </div>
  );
}
