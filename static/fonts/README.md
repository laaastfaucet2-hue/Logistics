# Local interface fonts

The complete, unmodified IBM Plex Sans Arabic fonts are bundled here for offline use:

| File | CSS weight |
| --- | --- |
| `IBMPlexSansArabic-Regular.woff2` | 400 |
| `IBMPlexSansArabic-Medium.woff2` | 500 |
| `IBMPlexSansArabic-SemiBold.woff2` | 600 |
| `IBMPlexSansArabic-Bold.woff2` | 700 |

Source: IBM's `@ibm/plex-sans-arabic` npm package, version **1.1.0**, `fonts/complete/woff2/`.
Original archive: https://registry.npmjs.org/@ibm/plex-sans-arabic/-/plex-sans-arabic-1.1.0.tgz
Upstream: https://github.com/IBM/plex
License: the original **SIL Open Font License 1.1** is preserved in `IBM-Plex-OFL.txt`.

These are complete Arabic/Latin fonts, not Latin-only web subsets. Arabic letters,
Eastern Arabic digits, Arabic decimal separator, and Latin digits were checked in
the fonts; actual Arabic glyph rendering is also checked in the browser acceptance.

`static/css/fonts.css` declares the faces. `static/css/theme.css` defines the shared
font stack. The native first-run screen embeds these same assets before the HTTP
server starts. No font is fetched from Google Fonts, a CDN, or IBM at runtime.

This is an interface font change. Excel/Word retain their existing document fonts,
letterhead colors, and the user's own logo; no restaurant branding is inserted.
