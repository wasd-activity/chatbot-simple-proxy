# Ensure these targets are not confused with files
.PHONY: install run

# install dependencies
install:
	uv pip install -r requirement.txt

# run the server, need to have a venv first
run:
	./.venv/bin/python ./main.py
