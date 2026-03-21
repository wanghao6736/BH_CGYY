# Overview

This repository contains a Python command-line application for interacting with
an external web service through a layered architecture. It combines typed
configuration loading, authenticated HTTP flows, response parsing, workflow
orchestration, and terminal-oriented output.

## Highlights

- Layered configuration loaded from a default profile plus optional profile-specific overrides
- Layered HTTP clients for signed API requests and SSO page flows
- Authentication pipeline with automatic refresh and per-profile credential persistence
- Parsing, workflow, and presentation layers kept separate
- Command-line entry points plus helper shell scripts for repeated execution

## Requirements

- Python 3.9+
- Dependencies are declared in `pyproject.toml`

## Installation

Install the project and its dependencies:

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

Or, if installed:

```bash
cgyy
```

Pass `--help` for the available commands:

```bash
cgyy --help
```

Detailed operator notes can be kept locally under `docs/` when needed.

## Project Structure

```text
src/
├── api/           # Endpoint definitions and API wrappers
├── auth/          # Service auth state and business token exchange
├── cli/           # Argument parsing, validation, and command dispatch
├── config/        # Typed settings and .env read/write helpers
├── core/          # Domain workflows and selection strategies
├── http/          # Shared HTTP transport helpers
├── parsers/       # Pure response parsers
├── presenters/    # Terminal formatting helpers
├── sso/           # SSO page flow and service adapters
├── tests/         # Automated tests
└── utils/         # Shared utilities
scripts/           # Shell helpers
docs/              # Detailed documentation
```

## License

This project is licensed under the [MIT License](LICENSE).
