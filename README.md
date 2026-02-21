# 🃏 Card Game Room

A multiplayer card game platform with **Lucky 7** and **Rummy** — playable in the browser with friends via a shared link. Built with Python (Flask) backend and a vanilla HTML/CSS/JS frontend, deployed via GitHub Actions.

---

## 🎮 Games

### ♦ Lucky 7
Start with Diamond 7. Each player extends the board by playing adjacent cards. First to discard all cards wins!
- 2–6 players
- Share a code to join

### 🂡 Rummy
Meld cards into sets and runs. Go out first to win the round!
- **Classic** — 7 cards, 1 deck
- **Gin Rummy** — 10 cards, 1 deck
- **Indian Rummy** — 13 cards, 2 decks
- 2–6 players, host sets the rules
- 3 scoring modes: Loser Pays, First to 100 Loses, Race to Target

---

## 🚀 Quick Start (Local)

```bash
git clone https://github.com/YOUR_USERNAME/card-game-room.git
cd card-game-room

# Install & run backend
pip install -r backend/requirements.txt
cd backend && python app.py

# Open frontend (in another terminal)
cd frontend && python -m http.server 8080
# Visit http://localhost:8080/games.html
```

---

## 🌐 Deploy (Play with Friends)

### Step 1 — Deploy Backend to Render (free)
1. Go to [render.com](https://render.com) → New → Web Service
2. Connect this GitHub repo
3. Render auto-detects `render.yaml` → click Deploy
4. Copy your URL: `https://card-game-room.onrender.com`

### Step 2 — Add GitHub Secret
Go to repo **Settings → Secrets and variables → Actions → New secret**
- Name: `BACKEND_URL`
- Value: your Render URL (no trailing slash)

### Step 3 — Enable GitHub Pages
Go to **Settings → Pages → Source: GitHub Actions**

### Step 4 — Trigger Deploy
```bash
git commit --allow-empty -m "Deploy"
git push
```

Your game room is live at:
```
https://YOUR_USERNAME.github.io/card-game-room/games.html
```

---

## 📁 Structure

```
card-game-room/
├── backend/
│   ├── app.py           # Flask server + Lucky 7 logic
│   ├── rummy.py         # Rummy game logic
│   └── requirements.txt
├── frontend/
│   ├── games.html       # Landing page — pick a game
│   ├── index.html       # Lucky 7
│   └── rummy.html       # Rummy
├── .github/
│   └── workflows/
│       ├── deploy-frontend.yml
│       └── backend-ci.yml
├── render.yaml
├── Procfile
└── fly.toml
```

---

## ⚙️ GitHub Actions

| Workflow | Triggers on | Does |
|----------|------------|------|
| `deploy-frontend.yml` | Push to `frontend/` | Injects backend URL → deploys to GitHub Pages |
| `backend-ci.yml` | Push to `backend/` | Runs tests → optional backend deploy |

---

## 💡 Notes

- Free Render instances sleep after 15 mins of inactivity — first load may take ~30s
- Games are stored in memory; server restart clears active games
- For production, replace the in-memory store with Redis

---

Made with ♦ ♥ ♣ ♠
