# Fonts

This directory is for local font files. LinkCanary uses Google Fonts CDN by default,
but you can add local woff2 files for offline use or better performance.

## Adding Local Fonts

1. Download the variable fonts from Google Fonts:
   - Space Grotesk: https://fonts.google.com/specimen/Space+Grotesk
   - Libre Franklin: https://fonts.google.com/specimen/Libre+Franklin

2. Place the woff2 files in this directory:
   - `SpaceGrotesk-Variable.woff2`
   - `LibreFranklin-Variable.woff2`

3. The CSS in `src/index.css` already includes @font-face declarations that will
   use these files when available.

## Current Setup

The app uses Google Fonts CDN for simplicity. The fonts are:
- **Space Grotesk** (300-700) - Display font for headings
- **Libre Franklin** (100-900) - Body font for content

Both fonts are loaded with `font-display: swap` for optimal performance.
