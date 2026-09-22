const COMMANDS = [
  {
    actionId: 'materials.open',
    phrases: [
      'відкрий матеріали',
      'відкрий мені матеріали',
      'покажи мені матеріали',
      'зайди в матеріали',
      'відкрий каталог матеріалів',
      'покажи матеріали',
      'перейди в матеріали',
      'перейди до матеріалів',
    ],
  },
  {
    actionId: 'fittings.open',
    phrases: [
      'відкрий фурнітуру',
      'відкрий мені фурнітуру',
      'покажи мені фурнітуру',
      'зайди у фурнітуру',
      'відкрий каталог фурнітури',
      'покажи фурнітуру',
      'перейди у фурнітуру',
      'перейди до фурнітури',
    ],
  },
  {
    actionId: 'mounting_nodes.open',
    phrases: [
      'відкрий монтажні вузли',
      'відкрий мені монтажні вузли',
      'покажи мені монтажні вузли',
      'зайди в монтажні вузли',
      'відкрий список монтажних вузлів',
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
