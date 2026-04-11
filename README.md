# Headlog

Personal thought capture system. Runs on localhost with zero dependencies.

```
ollama serve & python app.py
```

// Stop everything (kills Ollama + app ports)

```
lsof -ti:5959,7777,11434 | xargs kill -9 2>/dev/null; echo "stopped"
```

Nuke all Work Trees

git worktree list --porcelain | grep -B2 "claude/" | grep "worktree " | awk '{print $2}' | xargs -I{} git worktree remove {}
