#!/usr/bin/env bash

python3 -m venv venv &&\
venv/bin/python -m pip install --upgrade pip &&\
venv/bin/python -m pip install --upgrade setuptools wheel &&\
venv/bin/python -m pip install -r requirements.txt &&\
venv/bin/python -m pip install -e .
