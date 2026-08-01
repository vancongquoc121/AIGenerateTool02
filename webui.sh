#!/bin/bash

# uv sync --all-extras
uv run python ./webui.py --share --port 7861
# uv run python ./webui.py

# monitor/kill process on port 7861
# lsof -i :7861
# kill -9 <PID>