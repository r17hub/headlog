# Headlog

Personal thought capture system. Runs on localhost with zero dependencies.

```
python app.py
```


// Stop everything (kills any process on ports 5959 and 7777)

```
lsof -ti:5959,7777 | xargs kill -9 2>/dev/null; echo "stopped"
```