# Deployment guide (on-premise Linux server)

## Requirements

| | Recommended |
|---|---|
| OS | Ubuntu 22.04 / 24.04 (any systemd distro works) |
| Python | 3.11 or newer |
| GPU | NVIDIA with 12–16 GB VRAM for the default 14B model at Q4_K_M (~9 GB weights + context). CPU-only works but is slow; use a smaller GGUF and set `LLM_N_GPU_LAYERS=0` |
| Disk | ~15 GB for models + room for documents |
| Build tools | `build-essential`, `cmake` (llama-cpp-python compiles native code) |

## 1. Install

```bash
sudo useradd --system --no-create-home --shell /usr/sbin/nologin suhail
sudo mkdir -p /opt/suhail && sudo chown suhail:suhail /opt/suhail
sudo -u suhail git clone <your-repo-url> /opt/suhail
cd /opt/suhail && sudo -u suhail python3 -m venv venv

# CPU build:
sudo -u suhail venv/bin/pip install -r requirements.txt
# NVIDIA GPU build (the flag name has changed between llama-cpp-python releases:
# current versions use GGML_CUDA; check the project's README for your version):
CMAKE_ARGS="-DGGML_CUDA=on" sudo -E -u suhail venv/bin/pip install --no-cache-dir llama-cpp-python
```

The service file assumes the project lives in `/opt/suhail`; edit the paths in
`deploy/suhail.service` if you use a different location.

## 2. Models (the server never needs the internet)

On any machine **with** internet:

```bash
python -m scripts.download_models      # embedding model + ~9 GB GGUF into ./models
```

Copy the whole `models/` directory to `/opt/suhail/models/` on the server, owned by `suhail`.
With `HF_HUB_OFFLINE=1` (the default in `.env.example`) the server will never attempt a
download; a missing model produces an explicit error on the page instead.

## 3. Configure

```bash
cd /opt/suhail
sudo -u suhail cp .env.example .env && sudo chmod 600 .env
sudo -u suhail venv/bin/python -m scripts.hash_password   # paste the printed line into .env
```

Do not commit `.env`. Replace branding by setting `ASSETS_DIR` to a folder (outside the
repository) containing `header_logo.png`, `assistant_avatar.png`, `user_avatar.png` and
`favicon.png`.

## 4. Run as a service

```bash
sudo cp deploy/suhail.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now suhail
sudo systemctl status suhail
journalctl -u suhail -f            # application + audit logs
curl localhost:8501/_stcore/health # -> ok
```

Validate the hardening options on your distro with
`systemd-analyze verify /etc/systemd/system/suhail.service` and
`systemd-analyze security suhail`.

## 5. Put TLS in front

The app serves plain HTTP, so the admin password would cross the LAN unencrypted. Terminate
TLS with a reverse proxy (nginx, Caddy, or the organisation's existing gateway) and bind the
app to loopback by changing `--server.address=0.0.0.0` to `127.0.0.1` in the unit file.
Streamlit needs WebSocket support enabled on the proxy.

## 6. Load documents

Through the **Admin** tab, or in bulk:

```bash
sudo -u suhail venv/bin/python -m scripts.manage ingest /path/to/documents
```

Scanned PDFs without a text layer are rejected with a clear message; OCR them first.

## 7. Tune retrieval

Copy `evals/golden.jsonl`, replace it with 20–50 real questions (plus a few that the
documents *cannot* answer), then:

```bash
sudo -u suhail venv/bin/python -m scripts.eval_retrieval --cases my-questions.jsonl
```

It prints hit@k, MRR and the range in which `SIMILARITY_THRESHOLD` separates answerable
from unanswerable questions. Set that value in `.env` and restart.

If you change `EMBEDDING_MODEL`, `CHUNK_SIZE` or `CHUNK_OVERLAP`, rebuild the index and re-run
the evaluation:

```bash
sudo systemctl stop suhail
sudo -u suhail venv/bin/python -m scripts.manage reindex
sudo systemctl start suhail
```

## Backup and restore

Everything stateful lives in `data/` (Chroma database, registry, original files). Back it up
**while the service is stopped** (or from a filesystem snapshot) so the SQLite files are
consistent:

```bash
sudo systemctl stop suhail
sudo tar czf suhail-data-$(date +%F).tgz -C /opt/suhail data
sudo systemctl start suhail
```

Restore by extracting into `/opt/suhail` before starting the service. The original files
plus `reindex` can rebuild the vector index if the Chroma folder is ever lost.

## Upgrades

```bash
sudo systemctl stop suhail
cd /opt/suhail && sudo -u suhail git pull
sudo -u suhail venv/bin/pip install -r requirements.txt
sudo systemctl start suhail
```

Take a data backup first. After a Chroma major-version upgrade, run `reindex`.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Page shows "LLM weights not found" | `LLM_MODEL_PATH` wrong or `models/` not copied |
| Page shows "index was built with a different embedding model" | `EMBEDDING_MODEL` changed since documents were indexed; run `python -m scripts.manage reindex` |
| Page shows "Embedding model could not be loaded" | Model not in `HF_HOME` cache; run `scripts.download_models` and copy `models/` |
| Admin tab says it is disabled | `ADMIN_PASSWORD_HASH` empty in `.env` |
| Admin locked out | Five failed logins; wait five minutes (or restart the service) |
| Arabic PDF text comes out reversed or scrambled | Try `PDF_RTL_FIX=false` (some PDFs already extract in logical order), then re-ingest |
| Upload "No extractable text" | Scanned PDF; OCR it first |
| Slow first answer | The model loads on the first question; subsequent answers are faster |
