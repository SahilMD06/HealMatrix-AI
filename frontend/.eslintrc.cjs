module.exports = {
  root: true,
  env: { browser: true, es2022: true },
  extends: [
    'eslint:recommended',
    'plugin:react/recommended',
    'plugin:react/jsx-runtime',
    'plugin:react-hooks/recommended',
  ],
  ignorePatterns: ['dist', 'node_modules', '.eslintrc.cjs'],
  parserOptions: { ecmaVersion: 'latest', sourceType: 'module' },
  settings: { react: { version: 'detect' } },
  plugins: ['react-refresh'],
  rules: {
    // Disabled deliberately: this rule only guards dev-mode hot-reload, and it
    // fires on idiomatic patterns we use on purpose — a context file exporting
    // both its Provider and its `use*` hook, and a component file exporting its
    // cva `*Variants` helper. Co-locating these is standard React and has no
    // runtime cost; the trade-off is a slightly less granular HMR boundary.
    'react-refresh/only-export-components': 'off',
    'react/prop-types': 'off',
    'no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
  },
  overrides: [
    {
      // These run under Node during the build, not in the browser — the base
      // config's `env: { browser: true }` doesn't know `process`/`require` are
      // real globals here, not typos.
      files: ['vite.config.js', 'tailwind.config.js'],
      env: { node: true },
    },
  ],
}
