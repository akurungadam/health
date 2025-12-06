// patient_portal/tailwind.config.js

/** @type {import('tailwindcss').Config} */
const colors = require('tailwindcss/colors')
module.exports = {
  content: [
    './index.html',
    './src/**/*.{vue,js,ts,jsx,tsx}',
    './node_modules/frappe-ui/**/*.{js,ts,vue,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        lightBlue: colors.sky,
        warmGray: colors.stone,
        trueGray: colors.neutral,
        coolGray: colors.gray,
        blueGray: colors.slate,
      },
    },
  },
  plugins: [],
}
