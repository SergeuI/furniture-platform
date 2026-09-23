import { SYSTEM_PHRASES } from '../phrases/phraseLibrary.js';

function normalizeCommand(value) {
  return String(value || '')
    .trim()
    .toLocaleLowerCase('uk-UA')
    .replace(/[.,!?;:]+$/g, '')
    .replace(/\s+/g, ' ');
}

export function resolveAssistantCommand(input) {
  const normalizedInput = normalizeCommand(input);

  if (!normalizedInput) {
    return { success: false, reason: 'empty_command' };
  }

  for (const command of SYSTEM_PHRASES) {
    const matched = command.phrases.some(
      (phrase) => normalizeCommand(phrase) === normalizedInput,
    );

    if (matched) {
      return {
        success: true,
        actionId: command.actionId,
      };
    }
  }

  return {
    success: false,
    reason: 'unknown_command',
  };
}
