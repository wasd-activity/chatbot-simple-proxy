# Ensure these targets are not confused with files
.PHONY: install run clean check-env

# install dependencies
install:
	. .venv/bin/activate && pip install -r requirement.txt

# run the server
run:
	. .venv/bin/activate && python ./main.py
