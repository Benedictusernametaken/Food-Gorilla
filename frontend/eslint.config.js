module.exports = [
  {
    files: ["**/*.js"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "commonjs",
      globals: {
        process: "readonly",
        Buffer: "readonly",
        fetch: "readonly",
        __dirname: "readonly",
        console: "readonly"
      }
    },
    rules: {
      "no-unused-vars": "error",
      "no-undef": "error",
      "semi": ["error", "always"]
    }
  }
];