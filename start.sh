#!/bin/bash
export PYTHONUNBUFFERED=true
gunicorn app:app