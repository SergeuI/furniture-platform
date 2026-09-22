import React, { useState } from 'react';
import './AssistantShell.css';
import { executeAssistantAction } from './actions/actionRegistry.js';
import { resolveAssistantCommand } from './commands/commandResolver.js';

export default function AssistantShell() {
  const [isOpen, setIsOpen] = useState(false);
  const [commandText, setCommandText] = useState('');
  const [commandResult, setCommandResult] = useState('');

  function handleCommandSubmit(event) {
    event.preventDefault();

    const resolved = resolveAssistantCommand(commandText);

    if (!resolved.success) {
      setCommandResult(resolved.reason === 'empty_command' ? 'Введіть команду.' : 'Команду поки не розплізнано.');
      return;
    }

    const executed = executeAssistantAction(resolved.actionId);
    setCommandResult(executed.success ? 'Команду виконано.' : 'Не вдалося виконати команду.');
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
