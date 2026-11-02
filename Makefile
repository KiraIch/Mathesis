export PYTHONPATH=src
export PATH := $(HOME)/.elan/bin:$(PATH)

LIMIT ?= 10

.PHONY: test test-kernel test-all smoke pilot lean-smoke lean-pilot lean-replay lean-search lean-bench pantograph-setup pantograph-probe

test:
	python3 -m unittest discover -s tests -v

test-kernel:
	MATHESIS_KERNEL_TESTS=1 python3 -m unittest tests.test_lean_pilot -v

test-all: test test-kernel

smoke:
	python3 -m mathesis.cli smoke

pilot:
	python3 -m mathesis.cli pilot

lean-smoke:
	python3 scripts/lean_smoke.py

lean-pilot:
	python3 -m mathesis.cli lean-pilot

lean-replay:
	.venv/bin/python -m mathesis.cli lean-replay --limit $(LIMIT)

lean-search:
	.venv/bin/python -m mathesis.cli lean-search

lean-bench:
	.venv/bin/python -m mathesis.cli lean-bench --limit $(LIMIT)

pantograph-setup:
	if [ ! -d .pantograph ]; then git clone --depth 1 --branch dev https://github.com/leanprover/Pantograph.git .pantograph; fi
	cd .pantograph && lake build

pantograph-probe:
	.venv/bin/python scripts/pantograph_have_probe.py .pantograph/.lake/build/bin/repl
