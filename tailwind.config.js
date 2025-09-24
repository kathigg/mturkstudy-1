// tailwind.config.js
module.exports = {
  content: [
    "./src/**/*.{js,ts,jsx,tsx}",
    "./components/**/*.{js,ts,jsx,tsx}",
    "./pages/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brandYellow: "#f2a100",   // your custom yellow
        brandGreen: "#82b588",   // (optional) custom green
      },
    },
  },
  plugins: [],
}