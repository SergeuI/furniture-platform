import React, { useState } from 'react';
import './AssistantShell.css';
import { executeAssistantAction } from './actions/actionRegistry.js';

export default function AssistantShell() {
  const [isOpen, setIsOpen] = useState(false);

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
