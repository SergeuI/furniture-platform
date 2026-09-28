const RESPONSES = {
  'assistant.action.materials.open.success': 'Готово, відкрив матеріали.',
  'assistant.action.fittings.open.success': 'Готово, відкрив фурнітуру.',
  'assistant.action.fittings.hinges.open.success': 'Готово, відкрив завіси.',
  'assistant.action.fittings.drawer_slides.open.success': 'Готово, відкрив напрямні для шухляд.',
  'assistant.action.mounting_nodes.open.success': 'Готово, відкрив монтажні вузли.',
  'assistant.command.unknown': 'Я не розібрав, що ви сказали.',
  'assistant.command.empty': 'Введіть команду.',
  'assistant.command.error': 'Не вдалося виконати команду.',
};

export function getAssistantResponse(responseId) {
  return RESPONSES[responseId] || null;
}
