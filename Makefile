PYTHON ?= python3
CONFIG ?= examples/config.yaml
export PYTHONPATH := src

.PHONY: stage1 stage2 test clean

stage1:
	$(PYTHON) -m depgraph stage1 --config $(CONFIG)

stage2:
	$(PYTHON) -m depgraph stage2 --config $(CONFIG)

test:
	$(PYTHON) -m unittest discover -s tests -v

clean:
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
