# UNIVERSE is test50 (50 stocks), sp100 (S&P 100) or sp500, e.g. `make all UNIVERSE=sp100`.
UNIVERSE ?= sp500
PYTHON ?= python

.PHONY: setup test lint rank backtest sector-neutral sql charts excel all dashboard

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

# The same ranking and backtest with z-scores within GICS sector (outputs/<universe>/sector_neutral/).
sector-neutral:
	$(PYTHON) -m src.rank --universe $(UNIVERSE) --sector-neutral
	$(PYTHON) -m src.backtest --universe $(UNIVERSE) --sector-neutral

# Loads the results into SQLite and runs the queries in sql/ (outputs/<universe>/sql_results/).
sql:
	$(PYTHON) -m src.database --universe $(UNIVERSE)

charts:
	$(PYTHON) -m src.visualization --universe $(UNIVERSE)

excel:
	$(PYTHON) -m src.excel_export --universe $(UNIVERSE)

# Everything for one universe. Run `make dashboard` once after all universes are done.
all: rank backtest sector-neutral sql charts excel

dashboard:
	$(PYTHON) -m src.dashboard
