const RESPONSES = {
  'assistant.action.materials.open.success': 'Готово, відкрила матеріали.',
  'assistant.action.fittings.open.success': 'Готово, відкрила фурнітуру.',
  'assistant.action.mounting_nodes.open.success': 'Готово, відкрила монтажні вузли.',
  'assistant.command.unknown': 'Я поки не розумію цю команду.',
  'assistant.command.empty': 'Введіть команду.',
  'assistant.command.error': 'Не вдалося виконати команду.',
};

export function getAssistantResponse(responseId) {
  return RESPONSES[responseId] || null;
}
