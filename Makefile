# Makefile for Orbital
all: build

build:
	cd core && dub build
	cd frontend && dub build

test:
	cd core && dub test
	cd frontend && dub test

clean:
	rm -rf build/
	rm -rf .dub/
	rm -f dub.selections.json
	rm -rf contrib/setup/js_tmp/
	rm -rf data/templates/default/static/js/d3/
	rm -rf data/templates/default/static/js/highlight/
	rm -rf data/templates/default/static/js/rickshaw/

install:
	@echo "Implement me!"

.PHONY: build clean test install
