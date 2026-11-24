# Judge Tour explorer

Static, ungated Judge Tour for Checkable Coordinator. Live site: https://fe-fl-kent-private.fly.dev/

This directory is a static nginx explorer (espresso/brass/cream, phone-first PWA). It does not run Fe or Anvil. The reproducible tour is still `./scripts/e2e.sh --ci` at the repository root (eight stages, teardown last).

To rebuild `public/index.html` and the source tree/zip from the repo root:

```sh
python3 -m venv .venv
.venv/bin/pip install markdown
.venv/bin/python build.py
```

Do not commit `.venv/`, `public/tree/`, or `public/fe-fl-judge-tour.zip`. Those are generated. Do not put gate passwords, Fly tokens, or contest submission codes here.
