# Project Structure

This project is organized around a dedicated package called `sigma_crawler`.

## Current Layout

```text
.
├── sigma_crawler/
│   ├── __init__.py
│   ├── config.py
│   ├── fast.py
│   ├── expanded.py
│   ├── helpers.py
│   └── models.py
├── main.py
├── tests/
│   ├── test_main_output.py
│   └── test_product_urls.py
├── README.md
├── NOTES.md
├── PROJECT_STRUCTURE.md
├── requirements.txt
├── Dockerfile
└── .dockerignore
```

## Why This Structure

- `sigma_crawler/` contains all implementation code.
- `main.py` is a runnable entrypoint.
- `tests/` is isolated from implementation modules.
- The package boundary makes imports and ownership clear.

## Docker Run

Build image:

```bash
docker build -t sigma-crawler .
```

Run project:

```bash
docker run --rm sigma-crawler
```

Run tests in container:

```bash
docker run --rm sigma-crawler python -m pytest tests -q
```
