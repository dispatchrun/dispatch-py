.PHONY: install test dev fmt generate clean update-proto

PYTHON := python

all: test

install:
	export PIP_EXTRA_INDEX_URL=https://buf.build/gen/python
	$(PYTHON) -m pip install -e .

dev:
	export PIP_EXTRA_INDEX_URL=https://buf.build/gen/python
	$(PYTHON) -m pip install -e .[dev]

fmt:
	$(PYTHON) -m black .

test:
	$(PYTHON) -m unittest discover

.proto:
	mkdir -p $@

.proto/ring: .proto
	buf export buf.build/stealthrocket/ring --output=.proto/ring

.proto/dispatch: .proto
	buf export buf.build/stealthrocket/dispatch --output=.proto/dispatch

update-proto:
	$(MAKE) clean
	$(MAKE) generate

generate: .proto/ring .proto/dispatch
	buf generate --template buf.gen.yaml
	cd src && find . -type d | while IFS= read -r dir; do touch $$dir/__init__.py; done
	rm src/__init__.py

clean:
	rm -rf .proto
	find . -type f -name '*.pyc' -delete
	find . -type d -name '__pycache__' -exec rm -r {} \;
