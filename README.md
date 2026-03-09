## Overview

This repository contains a small command-line utility written in Python.
It provides a simple interface to interact with a remote HTTP-based service
and offers basic helpers for configuration, parsing responses, and displaying
results in a human-readable format.

## Features

- Configurable settings loaded from environment variables or a local `.env` file
- HTTP client with automatic retry and request signing
- Captcha recognition and verification pipeline
- Pluggable selection strategies for choosing among available options
- Response parsing utilities and presenter helpers for terminal output
- Shell scripts for polling workflows and desktop notifications (macOS)

## Requirements

- Python 3.9+
- Dependencies are declared in `pyproject.toml`

## Installation

Install the project and its dependencies (editable mode recommended for development):

```bash
pip install -e .
```

Or install directly:

```bash
pip install .
```

## Usage

Run the main entry point:

```bash
python -m src.main
```

Or, if installed via `pip install`:

```bash
cgyy
```

Pass `--help` for an overview of available sub-commands and options:

```bash
cgyy --help
```

See [`docs/README.md`](docs/README.md) for detailed configuration and usage instructions.

## Project Structure

```
src/
├── api/           # HTTP client and API endpoint wrappers
├── cli/           # Argument parsing, validation, and command dispatch
├── config/        # Settings loaded from environment / .env
├── core/          # Business logic, workflows, and strategies
├── parsers/       # Pure-function JSON response parsers
├── presenters/    # Human-readable terminal output formatters
├── utils/         # Cryptography, signing, OCR, and time helpers
└── tests/         # Parser tests and manual integration test scripts
scripts/           # Shell helpers for polling and notifications
docs/              # Detailed documentation and sample API responses
```

## License

This project is licensed under the [MIT License](LICENSE).
