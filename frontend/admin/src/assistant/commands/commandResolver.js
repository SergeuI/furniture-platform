import { SYSTEM_PHRASES } from '../phrases/phraseLibrary.js';

const DYNAMIC_PHRASE_MAPPINGS = new Map();

function normalizeCommand(value) {
  return String(value || '')
    .trim()
    .toLocaleLowerCase('uk-UA')
    .replace(/[.,!?;:]+$/g, '')
    .replace(/\s+/g, ' ');
}

export function setAssistantPhraseMappings(items) {
  DYNAMIC_PHRASE_MAPPINGS.clear();

  for (const item of Array.isArray(items) ? items : []) {
    const phrase = normalizeCommand(item?.phrase);
    const actionId = String(item?.action_id || '').trim();

    if (phrase && actionId) {
      DYNAMIC_PHRASE_MAPPINGS.set(phrase, actionId);
    }
  }
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

  const dynamicActionId = DYNAMIC_PHRASE_MAPPINGS.get(normalizedInput);

  if (dynamicActionId) {
    return {
      success: true,
      actionId: dynamicActionId,
    };
  }

  return {
    success: false,
    reason: 'unknown_command',
  };
}
