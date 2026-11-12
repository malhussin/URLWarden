# URLWarden

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](Dockerfile)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)](Dockerfile)
[![python-telegram-bot 21.6](https://img.shields.io/badge/python--telegram--bot-21.6-26A5E4?logo=telegram&logoColor=white)](requirements.txt)
[![VirusTotal API v3](https://img.shields.io/badge/VirusTotal-API%20v3-394EFF?logo=virustotal&logoColor=white)](https://docs.virustotal.com/reference/overview)

A self-hosted Telegram bot that checks links for malware and phishing with VirusTotal's security engines. It includes a local web dashboard and a strict user allowlist, and it needs no database or `.env` file.

---

## Features

| Command | What it does |
|---|---|
| `/start` | Shows the welcome message and usage help. |
| `/help` | Shows the same help text. |

To scan a link, send the bot a message containing only that URL, such as `https://example.com`. The bot replies `🔍 Scanning...`, then updates that message with the result:

| Verdict | Meaning |
|---|---|
| 🟢 **Safe** | No engine flagged the URL as malicious or suspicious. |
| 🟡 **Suspicious** | At least one engine flagged it as suspicious, and none as malicious. |
| 🔴 **Malicious** | At least one engine flagged it as malicious. |

The reply also shows the count from each engine category and a link to the full VirusTotal report.

- **Existing reports are reused.** If VirusTotal already knows the URL, the bot uses that report instead of submitting a new scan.
- **Results are cached for 1 hour.** Scanning the same URL again within that time uses no VirusTotal quota.
- **Quota is protected.** The bot stays under the free-tier limits and queues scans when several people use it at once.

> **Privacy note:** URLs submitted to VirusTotal are shared with its community. Don't scan links containing private tokens or personal data.

---

## Prerequisites

- **Docker** — [Docker Desktop](https://docs.docker.com/get-docker/) on macOS/Windows, or Docker Engine on Linux. Check with `docker --version`.
- **A Telegram account.**
- **A free VirusTotal account.**

You don't need a domain, HTTPS certificate, or open inbound port, because the bot only makes outbound connections to Telegram and VirusTotal.

---

## Create your Telegram bot

1. Open Telegram and start a chat with **[@BotFather](https://t.me/BotFather)**.
2. Send `/newbot`.
3. Choose a **display name**, e.g. `URLWarden`.
4. Choose a **username**. It must be unique and **must end in `bot`**, e.g. `my_urlwarden_bot`.
5. BotFather replies with your **HTTP API token**. It looks like this:

   ```
   123456789:ABCdefGhIJKlmNoPQRstuVwxyZ
   ```

> ⚠️ **Never commit this token.** Anyone holding it has full control of your bot. If it leaks, send `/revoke` to BotFather and generate a new one.

### Optional: a command menu

Send `/setcommands` to BotFather, pick your bot, and paste:

```
start - Show the welcome message
help - Show how to scan a link
```

---

## Get a VirusTotal API key

1. Sign up at **[virustotal.com](https://www.virustotal.com/gui/join-us)** and confirm your email.
2. Sign in, click your profile picture (top right), and choose **API key**, or go straight to <https://www.virustotal.com/gui/my-apikey>.
3. Copy the key.

To check that the key works, run this and confirm it prints JSON about the domain:

```bash
curl -H "x-apikey: <YOUR_KEY>" "https://www.virustotal.com/api/v3/domains/example.com"
```

The free public API has these limits:

| Limit | Value |
|---|---|
| Per minute | 4 requests |
| Per day | 500 requests |
| Use | Non-commercial only; commercial use needs a paid plan |

A URL VirusTotal already knows costs 1 request. A new URL costs at least 3, because the bot looks it up, submits it, and polls for the result.

> ⚠️ **Never commit this key.** Enter it only in the dashboard, which saves it in the gitignored `data/` folder.

---

## Find your Telegram user ID

**Access is restricted by numeric user ID.** If your ID isn't on the allowlist, the bot refuses to scan and replies `🚫 Sorry, you're not authorized to use this bot.`

Two ways to find yours:

1. **Message [@userinfobot](https://t.me/userinfobot).** It replies with your numeric ID.
2. **Ask your own bot.** Once the container is running, send your bot a URL. The refusal is logged with your ID:

   ```bash
   docker logs urlwarden 2>&1 | grep not_allowed
   # user=123456789 action=blocked reason=not_allowed
   ```

Allowlist changes take effect **immediately**, with no restart.

> **There is no admin role.** Everyone on the allowlist has the same access. An empty allowlist blocks every scan.

---

## Run with Docker

```bash
git clone <your-repo-url> URLWarden
cd URLWarden

docker build -t urlwarden .

docker run -d \
  --name urlwarden \
  -p 127.0.0.1:8080:8080 \
  -v urlwarden-data:/app/data \
  --restart unless-stopped \
  urlwarden
```

**Then finish setup in the dashboard:**

1. Open **<http://127.0.0.1:8080>**.
2. Under **Credentials**, paste your bot token and VirusTotal key, then click **Save Credentials**.
3. Under **Allowed Telegram Users**, enter your user ID and click **Add**.
4. Message your bot on Telegram and send a URL.

The bot checks for keys every 10 seconds and connects by itself once both are saved. Until then, the log repeats `Waiting for the Telegram bot token and VirusTotal API key`. **That is expected, not a crash.**

### Everyday commands

```bash
docker logs -f urlwarden      # follow the logs
docker restart urlwarden      # restart (needed after a token change)
docker stop urlwarden         # stop
docker start urlwarden        # start again
```

To update after pulling changes, replace the container. Your data stays in the volume:

```bash
docker rm -f urlwarden
docker build -t urlwarden .
# Then run the same docker run command as above.
```

### Deploy on a VPS

1. Install Docker (this example is for Ubuntu or Debian):

   ```bash
   curl -fsSL https://get.docker.com | sudo sh
   ```

2. Clone the repository on the server and run the commands above, using `sudo docker` if your user isn't in the `docker` group.
3. From **your own computer**, open an SSH tunnel and leave it running:

   ```bash
   ssh -L 8080:127.0.0.1:8080 you@your-server
   ```

4. Open <http://127.0.0.1:8080> on your computer and finish setup.

The bot keeps running after you close the tunnel.

### Run without Docker

Requires Python 3.12:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

The dashboard listens on <http://127.0.0.1:8080> only, and data is saved in the project's `data/` folder.

### Dashboard security

> ⚠️ **The dashboard has no login.** Anyone who can reach it can replace your API keys and change who may use the bot.

- It is published to `127.0.0.1:8080` only, so it is reachable from the host machine and not from your network.
- **Do not** change this to `-p 8080:8080`, open the port in a firewall, or put it behind a public reverse proxy.
- For remote access, use the SSH tunnel above or a private network such as Tailscale.
- Other users with access to the host machine can also reach it.

---

## Configuration

All settings are made in the dashboard:

| Setting | When it applies |
|---|---|
| Telegram bot token | After `docker restart urlwarden` (the first time it is set, the bot connects by itself) |
| VirusTotal API key | On the next scan |
| Allowed users | Immediately |

Limits are constants in the code. Rebuild the image after changing them:

| Constant | File | Default |
|---|---|---|
| `VT_MAX_PER_MINUTE` | `bot/main.py` | `4` |
| `VT_MAX_PER_DAY` | `bot/main.py` | `500` |
| `DEFAULT_TTL_SECONDS` (cache time) | `common/cache_store.py` | `3600` |
| `MAX_ENTRIES` (scan history size) | `common/usage_store.py` | `5000` |

---

## Persistent data and volumes

Everything that must survive a rebuild lives in the **`urlwarden-data`** Docker volume, mounted at `/app/data`:

| File | Contents | Back up? |
|---|---|---|
| `credentials.json` | Telegram token and VirusTotal key, unencrypted, owner-only permissions | **Yes** |
| `allowlist.json` | Allowed Telegram user IDs | **Yes** |
| `usage.json` | The latest 5,000 scans, shown in the dashboard | Optional |
| `cache/` | Scan results, reused for 1 hour | No |

To back up:

```bash
docker cp urlwarden:/app/data ./urlwarden-backup
```

The backup holds your live keys, so keep it out of any repo.

To reset everything, which permanently deletes your keys, allowlist, and history:

```bash
docker rm -f urlwarden
docker volume rm urlwarden-data
```

---

## Troubleshooting

**The bot doesn't reply at all.**
Run `docker logs -f urlwarden`. If you see `Waiting for the Telegram bot token`, one or both keys aren't saved, so add them in the dashboard. If the bot has started, confirm you're messaging the right `@username`.

**"🚫 Sorry, you're not authorized to use this bot."**
Your numeric ID isn't on the allowlist. Add it in the dashboard; no restart is needed.

**"❓ Please send a single, well-formed URL."**
The message must be only one link starting with `http://` or `https://`, with no other text.

**Logs show `Bot crashed` with `InvalidToken`.**
The token is wrong. Copy it from BotFather again and save it in the dashboard. The bot retries every 30 seconds.

**Logs show `409 Conflict`.**
The same token is running somewhere else. Stop the other copy.

**"VirusTotal rejected the API key."**
Paste the key into the dashboard again and check that it has no extra characters.

**"VirusTotal rate limit reached" or the daily quota message.**
The free limit was reached. Wait a minute, or until the next day for the daily quota.

**"VirusTotal scan did not finish in time."**
VirusTotal is busy. Send the link again shortly.

**The bot still behaves as if it has the old token.**
Run `docker restart urlwarden`.

**Dashboard won't load.**
Confirm the container is up with `docker ps`. On a VPS, confirm the SSH tunnel is running.

**`port is already allocated`.**
Port 8080 is in use. Use `-p 127.0.0.1:9090:8080` and open port 9090.

---

## License

Released under the [MIT License](LICENSE).

## Contributing

Issues and pull requests are welcome.

Before opening a PR:
- **Never commit the `data/` folder, a bot token, an API key, or a real Telegram user ID.**
- Build the image and confirm the container starts cleanly.
- To add another threat-intel source, implement `ThreatIntelProvider` from [`bot/providers/base.py`](bot/providers/base.py) and instantiate it in [`bot/main.py`](bot/main.py).

Useful entry points: [`app.py`](app.py) starts everything, [`bot/handlers.py`](bot/handlers.py) handles Telegram messages, [`bot/providers/virustotal.py`](bot/providers/virustotal.py) is the VirusTotal client, and [`dashboard/server.py`](dashboard/server.py) is the dashboard API.
