# Calculator

A dark-themed calculator for Android and desktop, built with Kivy. Its only dependency is Kivy.

- **Standard**: live result preview, percent that works like a pocket calculator, smart brackets, thousands separators and sign toggle.
- **Scientific**: sin, cos, tan, ln, log, √, x², xʸ, 1/x, |x|, n!, π and e, with a DEG/RAD switch. It shares its expression with Standard, so you can switch screens mid-calculation.
- **History**: the last 100 calculations, saved between launches. Tap one to load it back for editing.
- **Unit converter**: length, area, temperature and volume, with unit swap and negative temperatures. Units are picked from a dropdown on each unit button.
- **Adapts to any screen**: phones in portrait or landscape, split screen, tablets and resizable desktop windows (details below).
- **Keyboard support** on desktop:

  | Key | Action |
  |---|---|
  | digits, `+ - * / ^ % ! ( ) .` | type into the expression; the numeric keypad works too |
  | `Enter` or `=` | calculate |
  | `Backspace` | delete |
  | `Delete` | clear |
  | `Esc` | go back to the main screen, or clear when already there |

  In the converter: digits, `.`, `Backspace` and `Delete`.

## Run it

Requires Python 3.9 or newer.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

On Android you can also run `main.py` directly in Pydroid 3.

## Test it

The engine has no Kivy dependency, so the tests need nothing installed:

```bash
python -m unittest discover -s tests -t .
```

There are 80 tests covering evaluation, editing, formatting, the session, history and the converter.

## Project layout

```
main.py                    entry point (also what Buildozer and PyInstaller use)
buildozer.spec             Android build settings
calculator.spec            Windows build settings (PyInstaller)
.github/workflows/         CI: tests, Windows and Android builds, releases
calculator/
  app.py                   the app: screens, navigation, keyboard shortcuts, error log
  core/                    pure Python engine, no Kivy imports
    errors.py              user-facing exception types
    evaluator.py           tokenizer and safe recursive-descent parser (Decimal maths)
    expression.py          what each key does to the expression being typed
    formatting.py          result formatting, scientific notation, thousands grouping
    session.py             shared state for Standard and Scientific, key dispatch
    history.py             history store with JSON persistence
    number_entry.py        number typing for the converter
    converter.py           unit tables, conversion, converter state
  ui/
    theme.py               every colour, key style and layout size
    widgets.py             CalcKey, UnitButton, ContentColumn, Card, AutoFitLabel, HistoryItem
    keypads.py             keypad layouts as data, and the self-sizing Keypad widget
    dialogs.py             unit dropdown and clear-history confirmation
    icons.py               the icon font and the eight glyphs the app uses
    fonts/                 icons.ttf (Material Design Icons subset) and its licence notice
    assets/                app icon, Android adaptive icon layers, splash image
    screens/               one small class per screen
    kv/                    layout files, one per screen
tests/                     unit tests for the engine
project_AUDIT.md           every bug found, and how it was fixed
```

`core/` never imports Kivy, and `ui/` never contains calculation logic. A screen sends a key name to `Session.press("7")` and shows the text that comes back.

## How it works

- **Evaluation.** `evaluator.py` parses the expression itself instead of calling `eval`, so typed input can never run code. Numbers are `Decimal`, so `0.1 + 0.2` is exactly `0.3`. Errors are typed (`DivisionByZeroError`, `MathDomainError`, …) and carry a message that appears under the display. The expression stays editable after an error.
- **Percent.** `50%` is 0.5. `100 + 10%` is 110, because a percentage after `+` or `−` is a percentage of the left side.
- **Trigonometry.** In degrees, angles are reduced exactly before the calculation, so `sin(180)` is 0 and `tan(90)` reports "Undefined".
- **Display vs. data.** Thousands separators are added only when drawing text. The expression never contains commas.
- **Results.** Up to 12 significant digits. Very large or very small values appear as `1.5×10^20`, which can be typed back into an expression. `±` and `⌫` treat a result as one value, so they never change only its exponent.

## Responsive layout

Every screen reads three flags from `ui/screens/base.py`, and these update whenever the window changes size:

| Flag | When | Effect |
|---|---|---|
| `landscape` | width > 1.15 × height | Scientific uses a 7-column grid |
| `compact` | height < 520 dp | smaller display and card heights, tighter spacing |
| `row_mode` | landscape **and** compact | toolbar and display share one row above the keypad; the converter splits into two halves |

The keypad (`ui/keypads.py`) receives a height budget, `max_height`, from its screen's kv rule: the column height minus the header and display. It uses round keys when there is room and pills when the window is short, never exceeds the budget, and the display gets whatever height is left. Content is centred and capped at 460 dp wide (760 dp for wide layouts), so tablets and large desktop windows stay readable.

## Extending it

**Add a unit.** Add one line to the right category in `core/converter.py`, for example `_linear("Nautical Miles", "1852")` under Length. No UI change is needed.

**Add a category.** Add a `Category(...)` to `CATEGORIES`. A tab appears automatically, sized to its name.

**Add a calculator function.** Add the name to `FUNCTIONS` in `core/expression.py` (and to its regexes), and to `_FUNCTIONS` and `_apply_function` in `core/evaluator.py`. Then add a `KeySpec` in `ui/keypads.py`.

**Change the look.** Edit `ui/theme.py`. All colours, key styles and layout sizes are defined there.

## Deployment

### Automatic builds on GitHub (recommended)

`.github/workflows/build.yml` runs on GitHub Actions, and it works in a **private repository**:

| When | What happens |
|---|---|
| Every push or pull request | runs the tests, then builds the Windows app and the Android APK; the files are downloadable from the run's page |
| A tag like `v1.1.0` | does the same, then publishes both files as a GitHub Release |

**1. Before the first release**, set your own package ID in `buildozer.spec` (`package.domain = org.example`). It can never change once the app is on Google Play.

**2. Push the project to a new private repository** (create it on github.com first, without a README):

```bash
git init
git add .
git commit -m "Calculator 1.1.0"
git branch -M main
git remote add origin https://github.com/<your-name>/calculator.git
git push -u origin main
```

Open the **Actions** tab to watch the build. The first Android build takes about 20–30 minutes; later ones reuse a cache.

**3. Publish a version.** Set `__version__` in `calculator/__init__.py` (Android reads it from there), then tag the same number:

```bash
git tag v1.1.0
git push origin v1.1.0
```

The release contains `Calculator-windows.zip` and the Android `.apk`.

**4. Let anyone download it while the code stays private.** Releases in a private repository are visible only to people with access to it. To share the app publicly:

1. Create a **public** repository, e.g. `calculator-releases`, containing just a README.
2. Create a fine-grained personal access token (GitHub → Settings → Developer settings) with access to that repository only and **Contents: Read and write**.
3. In the private repository, open Settings → Secrets and variables → Actions:
   - add the secret `RELEASE_TOKEN` (the token);
   - add the variable `RELEASE_REPO` = `<your-name>/calculator-releases`.

From then on, each tag publishes the downloads to the public repository. Your code is never copied there.

**5. Google Play (optional).** Play needs a signed `.aab`. Create an upload key once, and keep the file and passwords somewhere safe outside the repository:

```bash
keytool -genkey -v -keystore release.keystore -alias calculator -keyalg RSA -keysize 2048 -validity 10000
base64 -w0 release.keystore      # copy the output
```

Add these secrets: `ANDROID_KEYSTORE_BASE64`, `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS` (`calculator`) and `ANDROID_KEY_PASSWORD`. Tagged builds then also produce a signed `.aab`. A Google Play developer account has a one-time fee.

**Cost.** Public repositories build for free. Private repositories use the monthly Actions minutes included with your plan; Windows minutes count double. See GitHub's billing page for current allowances.

### Building on your own machine

**Windows app:**

```bash
pip install -r requirements.txt pyinstaller
pyinstaller calculator.spec
```

The app is the whole `dist/Calculator` folder; run `Calculator.exe` inside it.

**Android:** Buildozer runs on Linux or macOS. On Windows, use WSL (Ubuntu).

```bash
pip install buildozer cython
buildozer android debug          # bin/*.apk, install it directly on a phone
```

### Notes for every platform

- Both orientations are supported, so there is no need to lock the orientation.
- The app needs no Android permissions. History lives in the app's private data folder.
- Unexpected errors are written to `error.log` in that folder instead of closing the app.
