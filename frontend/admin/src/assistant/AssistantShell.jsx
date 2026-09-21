import React, { useState } from 'react';
import './AssistantShell.css';

export default function AssistantShell() {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className='mp-assistant'>
      {isOpen && (
        <section className='mp-assistant__panel' aria-label='MP Assistant'>
          <header className='mp-assistant__header'>
            <div>
              <strong>MP Assistant</strong>
              <span>Помічник MP Furniture</span>
            </div>
            <button type='button' className='mp-assistant__close' onClick={() => setIsOpen(false)} aria-label='Закрити'>×</button>
          </header>
          <div className='mp-assistant__body'>
            <p>Вітаю Ф Я MP Assistant.</p>
            <p>Незабаром я допомагатиму працювати з MP Furniture.</p>
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
