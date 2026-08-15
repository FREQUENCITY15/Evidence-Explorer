# Contributing to Evidence Explorer

Evidence Explorer is an early public alpha. Small, evidence-backed changes are
more useful than broad rewrites.

## Before opening an issue

- Search existing issues first.
- Use synthetic or thoroughly sanitized evidence.
- Never post credentials, private transcripts, proprietary source, medical
  information, or other sensitive data.
- For suspected vulnerabilities, follow [SECURITY.md](SECURITY.md) instead of
  opening a public issue.

## Development setup

Python 3.12 or newer is supported.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
```

On Windows, `setup_project.bat` creates the project's Python 3.14 virtual
environment.

## Pull requests

1. Branch from `main`.
2. Keep the change narrowly scoped.
3. Add regression coverage for behavioural changes.
4. Run the complete offline suite.
5. Run `git diff --check`.
6. Explain the user impact, trust-boundary impact, and validation performed.

Changes to evidence parsing or governance must preserve these principles:

- malformed records and incomplete evidence remain distinct;
- `null`, `false`, and zero remain meaningful observed values;
- evidence citations resolve to stable record-local JSON Pointers;
- governance stays deterministic and separate from reliability;
- unknown invoked tools default to the conservative classification;
- untrusted content is never rendered as HTML;
- tests do not require Ollama, cloud services, or private data.

By submitting a contribution, you agree that it is licensed under the
[Apache License 2.0](LICENSE).

Be constructive and respectful. Harassment, discrimination, or disclosure of
another person's private information is not accepted.
