module.exports = {
  content: [
    "./templates/**/*.html",
    "./static/src/**/*.js",
    // Add other paths as needed
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          "900": "#17382c"  // Your custom green!
        }
      }
    }
  },
  plugins: [],
}