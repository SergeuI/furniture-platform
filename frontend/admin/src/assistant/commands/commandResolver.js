const COMMANDS = [
  {
    actionId: 'materials.open',
    phrases: [
      'відкрий матеріали',
      'покажи матеріали',
      'перейди в матеріали',
      'перейди до матеріалів',
    ],
  },
  {
    actionId: 'fittings.open',
    phrases: [
      'відкрий фурнітуру',
      'покажи фурнітуру',
      'перейди у фурнітуру',
      'перейди до фурнітури',
    ],
  },
  {
    actionId: 'mounting_nodes.open',
    phrases: [
      'відкрий монтажні вузли',
      'покажи монтажні вузли',
      'перейди до монтажних вузлів',
      'перейди в монтажні вузли',
    ],
  },
];

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

  for (const command of COMMANDS) {
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
