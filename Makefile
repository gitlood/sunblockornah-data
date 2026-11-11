# Local dev: hash-pinned venv, then the offline tests.
PIPE_VENV := pipeline/.venv
.PHONY: test
test:
	@test -x $(PIPE_VENV)/bin/python || { python3 -m venv $(PIPE_VENV) && $(PIPE_VENV)/bin/pip install -q --require-hashes -r pipeline/requirements.txt; }
	@cd pipeline && .venv/bin/python -m pytest -q -p no:cacheprovider tests
