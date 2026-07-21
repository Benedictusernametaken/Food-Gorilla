module.exports = [
  {
    files: ["**/*.js"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "commonjs"
    },
    rules: {
      "no-unused-vars": "error",
      "no-undef": "error",
      "semi": ["error", "always"]
    }
  }
];