PYTHON ?= python3
CONFIG ?= examples/config.yaml
export PYTHONPATH := src

.PHONY: install run test clean

install:
	$(PYTHON) -m pip install -r requirements.txt

run:
	$(PYTHON) -m depgraph --config $(CONFIG)

test:
	$(PYTHON) -m unittest discover -s tests -v

clean:
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
