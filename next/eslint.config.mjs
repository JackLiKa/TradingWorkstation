import next from 'eslint-config-next';

/** @type {import('eslint').Linter.Config[]} */
export default [
  ...next,
  {
    rules: {
      'react-hooks/exhaustive-deps': 'warn',
    },
  },
];
