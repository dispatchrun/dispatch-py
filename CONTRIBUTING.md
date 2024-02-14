# Contributing

## Setup

```
make dev
```

## Test

```
make test
```

## Coverage

```
make coverage
```

In addition to displaying the summary in the terminal, this command generates an
HTML report with line-by-line coverage. `open .coverage-html/index.html` and
click around. You can refresh your browser after each `make coverage` run.

## Style

Formatting is done with `black`. Run `make fmt`.

Docstrings follow the [Google style][docstrings]. All public entities should
have a docstring attached.

[docstrings]: https://google.github.io/styleguide/pyguide.html#s3.8-comments-and-docstrings

## Documentation

API reference documentation is automatically built on merges to `main` and new
tagged version. To view the generated documentation locally:

```
make local-docs
```
