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
      'no-undef': 'error',
    },
  },
];
