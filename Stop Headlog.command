#!/bin/bash
lsof -ti:5959,7777,11434 | xargs kill -9 2>/dev/null
echo "Headlog stopped."
sleep 1
