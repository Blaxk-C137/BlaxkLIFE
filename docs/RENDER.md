# Deploy BLXVERSE on Render (CPU only)

## Ready-to-deploy setup

This repository includes `render.yaml`, `.python-version`, and a runtime
`requirements.txt`. The game requires **no GPU, PyTorch, CUDA, Node build,
external database, or model download**. Python runs the simulation; the player's
browser renders the world. Remote dialogue stays offline unless you configure a provider API key.

The Blueprint provisions a **paid Starter web service plus a 1 GB persistent
disk**. Review Render's current charges before confirming. Nothing has been
provisioned or billed by this code change.

### Deploy with the Blueprint (recommended)

1. Put the contents of this repository in a GitHub or GitLab repository you own.
   `render.yaml`, `run_server.py`, and `requirements.txt` should be at its root.
   Do not upload `.env`, local save data, API keys, or a virtual environment.
2. In Render, select **New → Blueprint** and connect that repository.
3. Review the resources: one `blxverse` Python web service, Starter plan, one
   persistent disk mounted at `/var/data`. Confirm only when ready for the cost.
4. Deploy. Wait for the service to become healthy, then open its HTTPS URL.
5. The browser prompts for a login:
   - **Username:** `blxverse`
   - **Password:** the generated value of `BLXVERSE_ACCESS_PASSWORD` in the
     service's **Environment** settings in Render.
6. The first deployment starts fresh; your local save is not uploaded automatically.
   Create your character. The save is stored at
   `/var/data/blxverse/saves/world.json` and resumes after restart or deploy.

If this project is nested inside a larger repository, set the web service's
**Root Directory** to the folder containing `run_server.py`, and point the
Blueprint setup at the correct `render.yaml` path.

### Equivalent manual Web Service settings

| Setting | Value |
| --- | --- |
| Runtime | Python 3 |
| Root Directory | blank if `run_server.py` is in the repo root |
| Build command | `pip install -r requirements.txt` |
| Start command | `python -u run_server.py` |
| Health check | `/api/health` |
| Instances | **1** |
| Instance type | Starter or another paid CPU plan supporting disks |
| Persistent disk | mount `/var/data`, size 1 GB |
| `BLXVERSE_HOST` | `0.0.0.0` |
| `BLXVERSE_DATA_DIR` | `/var/data/blxverse` |
| `BLXVERSE_LLM_DISABLED` | `0` (remote dialogue still needs an API key) |
| `BLXVERSE_ACCESS_PASSWORD` | a long random password you generate |

Use the committed `.python-version` (`3.13`) so Render selects the latest patch
of the tested Python series. Do **not** set `BLXVERSE_PORT` on Render: the app
reads Render's injected `PORT`. Locally, `--port` / `BLXVERSE_PORT` takes
precedence over `PORT`, then the default is `8000`.

## Important boundaries

- **One world, one player, one process.** This is still a single-player game,
  not an account-based multiplayer backend. Every authenticated browser shares
  the same player and save. Do not add Gunicorn workers, replicas, or autoscaling:
  independent processes would fork the in-memory simulation and overwrite saves.
- **Private by default.** The Blueprint generates a password and protects the
  game page, assets, saves, and API with browser HTTP Basic authentication.
  `/api/health` alone stays public for Render. Always use HTTPS. To rotate access,
  change `BLXVERSE_ACCESS_PASSWORD` and redeploy; browsers may need to be closed
  and reopened to forget cached credentials. This is a single shared password,
  not individual user accounts or a full identity system.
- **Free is only a disposable demo.** To use a free service, choose Free manually,
  omit the disk, and use `BLXVERSE_DATA_DIR=data`. It can run but **saves are not
  durable** across redeploys/replacements, and idle spin-down pauses the world.
  The checked-in Blueprint intentionally does not select this configuration.
- **Only the disk path persists.** Do not save under the repository directory
  on a paid deployment; all save and audit paths use `BLXVERSE_DATA_DIR`.
- **Back up the world.** Download `/api/save` while logged in, especially before
  changing configuration or replacing a service. The app rotates a local `.bak`
  file, but this is not a substitute for off-service backups.
- **No offline catch-up.** A stopped instance resumes the saved game clock; it
  does not simulate the time the service was down. Paid hosting continues the
  simulation while running, even if the browser is closed.
- **Browser voice support still varies.** HTTPS supports browser speech features,
  but hosting cannot add missing browser SpeechRecognition support. Typed input
  remains available.

BlaxkVille 0.3 retains this same deployment setup. The city name, offline voice
bank and UX changes require no GPU, extra runtime dependency, or database. See
[`BLAXKVILLE_0.3.md`](BLAXKVILLE_0.3.md) for the current gameplay repair notes.

## What changed for hosting

- `PORT` support while retaining local `--port` overrides and `0.0.0.0` binding.
- A writable save-directory check before accepting traffic (misconfigured disks
  fail visibly in deployment logs, not after a player starts).
- SIGTERM/SIGINT stop the tick thread, drain HTTP handlers, and force a final save
  before exiting successfully. Render gets up to 30 seconds for shutdown.
- Monotonic simulation timing, and world lookup inside the simulation lock.
- Maximum 32 request-handler threads, 15-second socket idle/body timeout, and
  closure of oversized-body/unauthenticated connections.
- Static file real-path confinement, including symlinks.
- Optional password gate, generated automatically by the Blueprint.

No simulation, navigation, or canvas renderer rewrite was necessary for CPU
hosting. Keeping one process also avoids breaking movement authority.

## Verification and CPU check

Run an isolated deployment check without touching your real world:

```bash
python3 scripts/render_check.py --seconds 30 --output docs/render-check.json
```

It boots with **only `PORT`**, a temporary simulated disk mount, and password
protection; creates a 60-resident world; runs at 4× with four state polls per
second; sends SIGTERM; restarts with the same directory; and verifies player,
clock, paused speed, calendar, journal, and save export.

A local sandbox run on 2026-10-17 (Python 3.13.16) recorded:

| Measurement | Result |
| --- | --- |
| Duration / requests | 30.22 s / 120 state requests |
| CPU, % of one full core | 4.7% |
| Peak sampled server resident memory | 28.45 MiB |
| State response p50 / p95 | 4.38 / 6.49 ms |
| Shutdown + same-disk recovery | PASS |

These are **short local measurements**, not results on Render hardware, an
all-day stress test, or a multiplayer capacity guarantee. Browser graphics CPU
is not included. Inspect Render's CPU/memory metrics after deployment and repeat
this check there if desired; it creates a temporary test world, not the live one.

Full verification for this release: **85/85 tests passed**, Ruff and Python
compile checks passed. An authenticated Chromium session loaded the game and
Calendar with zero page errors or HTTP failures; the movement probe passed.

Additional tests:

```bash
python3 -m pip install pytest ruff  # developer tools, not runtime dependencies
pytest -q
ruff check blxverse tests scripts
```

## Troubleshooting

- **No open port / unhealthy:** use `python -u run_server.py`, remove any old
  `BLXVERSE_PORT` override, and inspect logs for `serving on http://0.0.0.0:...`.
- **Save disappears:** verify the persistent disk is attached and
  `BLXVERSE_DATA_DIR=/var/data/blxverse`. A Free service cannot provide this disk.
- **Login keeps appearing:** use username `blxverse` and the actual generated
  password from Render, not the variable's name. Clear cached browser credentials
  if the password changed.
- **Two visitors move one avatar:** expected shared-world behavior. Keep access
  private; separate users need separate service instances/disks or a future
  session/world-isolation redesign.
- **Permission error on startup:** the mounted data directory must be writable.
  Do not set it to the read-only source or a nonexistent external volume.
- **Browser GET works but your curl gets 401:** authenticate API requests with
  `curl -u 'blxverse:YOUR_PASSWORD' https://YOUR_SERVICE.onrender.com/api/state`.
- **Optional external LLM:** remove/set `BLXVERSE_LLM_DISABLED=0`, add your API key
  as a Render secret, and configure the provider URL/model if needed. This uses
  a remote API, not Render GPU compute, may add latency, and may incur provider
  charges. The deterministic composer requires no key.

## Render references

- Web services and port binding: https://render.com/docs/web-services
- Blueprint schema: https://render.com/docs/blueprint-spec
- Persistent disks: https://render.com/docs/disks
- Health checks: https://render.com/docs/health-checks
- Python version selection: https://render.com/docs/python-version

## Optional Gemini dialogue (0.4+)

In Render → Environment, add `GEMINI_API_KEY`, optionally set
`GEMINI_MODEL=gemini-3.5-flash-lite`, and set `BLXVERSE_LLM_DISABLED=0`.
Restart/redeploy after editing. An older Blueprint may have left the disable
flag at `1`; adding a key alone will not override that flag. Do not put keys in
client files. Without a key the game runs locally composed dialogue, CPU-only.
Calls use Gemini-generated text with browser speech, not Gemini Live audio.
Provider requests have a six-second timeout with offline fallback. Key/quota/
billing/privacy are your responsibility; actual model spend is not measured here.
