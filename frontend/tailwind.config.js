/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx}",
    "./components/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: "#0b0e11",
        panel: "#12161c",
        border: "#1f2530",
        bull: "#16c784",
        bear: "#ea3943",
        neutral: "#f0b90b",
      },
    },
  },
  plugins: [],
};
