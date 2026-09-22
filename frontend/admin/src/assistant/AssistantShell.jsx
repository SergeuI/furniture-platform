import React, { useState } from 'react';
import './AssistantShell.css';
import { executeAssistantAction } from './actions/actionRegistry.js';
import { resolveAssistantCommand } from './commands/commandResolver.js';
import { getAssistantResponse } from './responses/responseRegistry.js';
import { ASSISTANT_STATES } from './state/assistantState.js';
import { createBrowserSpeechRecognition, isBrowserSpeechRecognitionSupported } from './voice/browserSpeechRecognition.js';
import { isBrowserSpeechSynthesisSupported, speakBrowserText } from './voice/browserSpeechSynthesis.js';
import { fetchAssistantVoice } from './voice/assistantVoiceClient.js';

export default function AssistantShell() {
  const [isOpen, setIsOpen] = useState(false);
  const [commandText, setCommandText] = useState('');
  const [commandResult, setCommandResult] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [assistantState, setAssistantState] = useState(ASSISTANT_STATES.IDLE);

  function handleVoiceInput() {
    if (!isBrowserSpeechRecognitionSupported()) {
      setAssistantState(ASSISTANT_STATES.ERROR);
      setCommandResult('Voice recognition is not supported in this browser.');
      return;
    }

    let recognitionFailed = false;
    const recognition = createBrowserSpeechRecognition({
      onResult: (transcript) => {
        setCommandText(transcript);
        setCommandResult('');
      },
      onError: () => {
        recognitionFailed = true;
        setAssistantState(ASSISTANT_STATES.ERROR);
        setCommandResult('Voice recognition failed. Please try again.');
      },
      onEnd: () => {
        setIsListening(false);
        if (!recognitionFailed) {
          setAssistantState(ASSISTANT_STATES.IDLE);
        }
      },
    });

    if (!recognition) {
      return;
    }

    setIsListening(true);
    setAssistantState(ASSISTANT_STATES.LISTENING);
    setCommandResult('');

    try {
      recognition.start();
    } catch {
      setIsListening(false);
      setAssistantState(ASSISTANT_STATES.ERROR);
      setCommandResult('Could not start microphone.');
    }
  }

  async function speakAssistantResponse(text, finalState = ASSISTANT_STATES.SUCCESS) {
    let audioUrl = null;

    try {
      const blob = await fetchAssistantVoice(text);
      audioUrl = URL.createObjectURL(blob);
      const audio = new Audio(audioUrl);
      audio.addEventListener('ended', () => { URL.revokeObjectURL(audioUrl); setAssistantState(finalState); }, { once: true });
      audio.addEventListener('error', () => URL.revokeObjectURL(audioUrl), { once: true });
      setAssistantState(ASSISTANT_STATES.SPEAKING);
      await audio.play();
      return;
    } catch {
      if (audioUrl) {
        URL.revokeObjectURL(audioUrl);
      }

      if (isBrowserSpeechSynthesisSupported()) {
        setAssistantState(ASSISTANT_STATES.SPEAKING);
        const started = speakBrowserText(text, {
          onEnd: () => setAssistantState(finalState),
          onError: () => setAssistantState(ASSISTANT_STATES.ERROR),
        });
        if (!started) {
          setAssistantState(ASSISTANT_STATES.ERROR);
        }
      } else {
        setAssistantState(ASSISTANT_STATES.ERROR);
      }
    }
  }

  function handleCommandSubmit(event) {

    event.preventDefault();

    setAssistantState(ASSISTANT_STATES.PROCESSING);
    const resolved = resolveAssistantCommand(commandText);

    if (!resolved.success) {
      const responseText = getAssistantResponse(resolved.reason === 'empty_command' ? 'assistant.command.empty' : 'assistant.command.unknown');
      setAssistantState(resolved.reason === 'empty_command' ? ASSISTANT_STATES.IDLE : ASSISTANT_STATES.ERROR);
      setCommandResult(responseText);
      if (resolved.reason === 'unknown_command') {
        void speakAssistantResponse(responseText, ASSISTANT_STATES.ERROR);
      }
      return;
    }

    setAssistantState(ASSISTANT_STATES.EXECUTING);
    const executed = executeAssistantAction(resolved.actionId);
    setAssistantState(executed.success ? ASSISTANT_STATES.SUCCESS : ASSISTANT_STATES.ERROR);
    const resultText = getAssistantResponse(executed.success ? `assistant.action.${resolved.actionId}.success` : 'assistant.command.error');
    setCommandResult(resultText);

    if (executed.success) {
      void speakAssistantResponse(resultText);
    }
  }

  return (
    <div className='mp-assistant'>
      {isOpen && (
        <section className='mp-assistant__panel' aria-label='MPFC Assistant'>
          <header className='mp-assistant__header'>
            <div>
              <strong>MPFC Assistant</strong>
              <span>Помічник MPFC</span>
            </div>
            <button type='button' className='mp-assistant__close' onClick={() => setIsOpen(false)} aria-label='Закрити'>×</button>
          </header>
          <div className='mp-assistant__body'>
            <p>Вітаю! Я MPFC Assistant.</p>
            <p>Допоможу вам працювати з MPFC.</p>
            <form onSubmit={handleCommandSubmit} style={{ display: 'flex', gap: '8px', marginTop: '12px' }}>
              <input
                type='text'
                value={commandText}
                onChange={(event) => setCommandText(event.target.value)}
                placeholder='Напишіть команду...'
                aria-label='Команда для PMPC Assistant'
                style={{ flex: 1, minWidth: 0 }}
              />
              <button type='submit'>Виконати</button>
              <button type='button' onClick={handleVoiceInput} disabled={isListening}>{isListening ? 'Listening...' : 'Mic'}</button>
            </form>
            {commandResult && <p role='status'>{commandResult}</p>}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '12px' }}>
                <button type='button' onClick={() => executeAssistantAction('materials.open')}>Матеріали</button>
                <button type='button' onClick={() => executeAssistantAction('fittings.open')}>Фурнітура</button>
                <button type='button' onClick={() => executeAssistantAction('mounting_nodes.open')}>Монтажні вузли</button>
              </div>
          </div>
        </section>
      )}

      <button type='button' className='mp-assistant__launcher' onClick={() => setIsOpen((value) => !value)} aria-expanded={isOpen}>
        <span className='mp-assistant__mark'>MP</span>
        <span>Assistant</span>
      </button>
    </div>
  );
}
