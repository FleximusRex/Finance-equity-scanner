# Use UNIVERSE=test50 for the 50-stock set, e.g. `make backtest UNIVERSE=test50`.
UNIVERSE ?= sp500
PYTHON ?= python

.PHONY: setup test lint rank backtest charts dashboard

setup:
	$(PYTHON) -m pip install -r requirements.txt ruff

test:
	$(PYTHON) -m pytest -q

lint:
	ruff check src tests

rank:
	$(PYTHON) -m src.rank --universe $(UNIVERSE)

backtest:
	$(PYTHON) -m src.backtest --universe $(UNIVERSE)

charts:
	$(PYTHON) -m src.visualization --universe $(UNIVERSE)

dashboard:
	$(PYTHON) -m src.dashboard
