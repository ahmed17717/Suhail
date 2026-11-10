.PHONY: install dev run test lint format models eval clean

install:  ## production install (needs a C++ toolchain for llama-cpp-python)
	pip install -r requirements.txt

dev:  ## lightweight dev/test environment (no torch, no llama.cpp)
	pip install -r requirements/dev.txt

run:  ## start the web app
	streamlit run app.py

test:  ## unit + UI smoke tests with coverage
	python -m pytest --cov

lint:  ## static checks (what CI runs)
	ruff check .
	ruff format --check .

format:  ## auto-fix formatting and safe lint issues
	ruff format .
	ruff check . --fix

models:  ## download embedding model + LLM (needs internet)
	python -m scripts.download_models

eval:  ## measure retrieval quality against evals/golden.jsonl
	python -m scripts.eval_retrieval

clean:
	rm -rf .pytest_cache .ruff_cache .coverage htmlcov
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
