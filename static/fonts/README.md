# Local interface fonts

The approved interface font is **Changa**, bundled here for fully offline use:

| File | CSS weight |
| --- | --- |
| `Changa-Regular.woff2` | 400 |
| `Changa-Medium.woff2` | 500 |
| `Changa-SemiBold.woff2` | 600 |
| `Changa-Bold.woff2` | 700 |

Source: Google Fonts `google/fonts` repository, `ofl/changa/Changa[wght].ttf`
(variable font, weight axis 200–800), instanced to the four canonical static
weights with `fonttools.varLib.instancer` — no glyph subsetting, the complete
Arabic/Latin character set is preserved.

Upstream: https://github.com/googlefonts/changa-vf
License: the original **SIL Open Font License 1.1** is preserved in `Changa-OFL.txt`.

These are complete Arabic/Latin fonts, not Latin-only web subsets. Arabic letters,
Eastern Arabic digits, the Arabic decimal separator, and Latin digits were checked
in the files; actual Arabic glyph rendering is also checked in the browser acceptance.

`static/css/fonts.css` declares the faces. `static/css/theme.css` defines the shared
font stack. The native first-run screen embeds these same assets before the HTTP
server starts. No font is fetched from Google Fonts or any CDN at runtime.

This is an interface font change only. Excel/Word retain their existing document
fonts, letterhead colors, and the user's own logo.
