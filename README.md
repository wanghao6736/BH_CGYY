# Overview

`buaa-cgyy` is a layered Python client for BUAA CGYY venue reservation. It
provides a CLI-first workflow for profile management, authentication refresh,
availability queries, reservation submission, order handling, payment target
generation, notifications, and optional desktop UI support.

## Highlights

- Default installation is CLI-only; the desktop UI is an optional extra
- Profile layering over `.env`, `.env.profiles/<name>.env`, and process env
- Signed CGYY API client plus SSO / cashier page-flow clients
- Automatic auth refresh, reservation submission, and payment target resolution
- Mobile payment returns a final `weixin://...` scheme; desktop payment returns `schoolPayUrl`
- Shared notifier for macOS and Bark / iOS

## Requirements

- Python 3.9+

## Installation

Install the smallest CLI runtime:

```bash
pip install -e .
```

Or:

```bash
pip install .
```

Install the OCR-enabled CLI:

```bash
pip install -e ".[ocr]"
```

Or:

```bash
pip install ".[ocr]"
```

Install the optional desktop UI:

```bash
pip install -e ".[ocr,ui]"
```

Or:

```bash
pip install ".[ocr,ui]"
```

`ddddocr` / `opencv-python-headless` / `Pillow` are only included by the `ocr`
extra. `PySide6` is only included by the `ui` extra. Base installation keeps a
lighter CLI available by default.

## Usage

Run the CLI:

```bash
python -m src.main --help
```

Or, if installed:

```bash
cgyy --help
```

Typical commands:

```bash
cgyy info -d 2026-04-01
cgyy reserve -P alice -d 2026-04-01 -s 18:00 -n 2
cgyy pay -t D260331000665 --mode desktop
cgyy pay -t D260331000665 --mode mobile
```

Payment behavior is intentionally split:

- `desktop`: return `schoolPayUrl`; the user opens the page and chooses a payment method
- `mobile`: resolve the final `weixin://...` scheme for direct jump or Bark notification deep link

Launch the desktop workbench only after installing the `ui` extra:

```bash
python -m src.ui.main
```

Or:

```bash
cgyy-ui
```

## Packaging

This repository includes `uv + Nuitka` build scripts with three targets:

- `scripts/build_cli_lite.sh`: smallest CLI, excludes OCR and UI dependent commands
- `scripts/build_cli_full.sh`: full CLI, includes reservation and captcha flows
- `scripts/build_ui_app.sh`: macOS desktop app bundle

Recommended build order:

```bash
./scripts/build_cli_lite.sh
./scripts/build_cli_full.sh
./scripts/build_ui_app.sh
```

Both CLI scripts default to `onefile` for minimum artifact size. If a build needs
easier troubleshooting first, switch temporarily to standalone mode:

```bash
CGYY_NUITKA_MODE=standalone ./scripts/build_cli_full.sh
```

Runtime config discovery for packaged binaries:

- Default source run: project root
- Compiled binary: executable directory, or the directory containing the `.app` bundle on macOS
- Override: set `CGYY_ROOT=/path/to/config-root`

Additional local operator notes may be kept under `docs/` when needed.

## Project Structure

```text
src/
├── api/           # Endpoint definitions and API wrappers
├── auth/          # Auth state, token exchange, and cashier bootstrap
├── cli/           # Argument parsing, validation, and command dispatch
├── config/        # Typed settings and .env read/write helpers
├── core/          # Reservation and payment workflows
├── http/          # Shared HTTP transport and header profiles
├── notifier.py    # Shared macOS / Bark notification entry point
├── parsers/       # Pure response parsers
├── presenters/    # Terminal formatting helpers
├── sso/           # SSO page flow and service adapters
├── ui/            # Optional PySide6 desktop workbench
├── tests/         # Automated tests
└── utils/         # Shared utilities
scripts/           # Shell helpers and polling wrappers
docs/              # Detailed documentation
```

## License

This project is licensed under the [MIT License](LICENSE).
