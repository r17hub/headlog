#!/bin/bash
cd ~/dev/r17/headlog || exit 1

ollama serve &>/dev/null &
python3 app.py &

sleep 2
open http://localhost:7777

wait
