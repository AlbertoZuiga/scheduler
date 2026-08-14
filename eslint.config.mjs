import js from '@eslint/js';
import globals from 'globals';

export default [
  {
    files: ['app/static/js/**/*.js'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'script',
      globals: {
        ...globals.browser,
        showInlineAlert: 'readonly',
        showConfirmDialog: 'readonly',
      },
    },
    rules: {
      ...js.configs.recommended.rules,
      'no-undef': 'error',
      'no-unused-vars': 'error',
      'eqeqeq': ['error', 'always'],
      'no-var': 'error',
      'prefer-const': 'error',
      'no-implicit-globals': 'error',
      'require-await': 'error',
      'no-shadow': 'warn',
    },
  },
  {
    // main.js define los globals públicos (showInlineAlert, showConfirmDialog, etc.)
    // de forma intencional: no aplica no-implicit-globals ni no-redeclare.
    files: ['app/static/js/main.js'],
    rules: {
      'no-implicit-globals': 'off',
      'no-redeclare': 'off',
    },
  },
];
