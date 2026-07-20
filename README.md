# DemoSat-1 Mission Telemetry System

End-to-end NASA-style real-time spacecraft telemetry system: a simulated
satellite downlinks CCSDS Space Packets over a lossy UDP "space link" into a
ground segment (decode, limit checking, Redis Streams bus, TimescaleDB
archive) visualized live in **NASA OpenMCT** — the open-source mission
control framework used at JPL and Ames.

> Work in progress — full architecture, screenshots, and commanding land at
> the end of the build (Milestones M6–M8).

## Quickstart

```bash
docker compose up --build -d
```

Then open **<http://localhost:8080>** — that single port serves OpenMCT and
reverse-proxies the telemetry API (`/api`) and the realtime WebSocket
(`/ws`). Nothing else needs to be exposed.

```bash
docker compose logs -f ingest     # watch decoded telemetry stream in
docker compose down               # stop everything
```

## Running alongside other Docker projects

This stack is built to share a Docker engine without disturbing anything
else on the machine — it claims one port, caps its own resources, and never
starts itself uninvited.

| Property | Value |
|---|---|
| Compose project | `demosat-groundstation` |
| Network | `demosat_net` |
| Volume | `demosat_timescale-data` |
| Published host ports | **8080 only** |
| Resource ceiling | ~2 GB RAM / 3 CPUs (idles ~140 MiB) |
| Restart policy | `on-failure:3` — bounded, and does **not** auto-start at Docker boot |

Everything is explicitly named rather than derived from the directory name,
so renaming or cloning the folder can't collide with another project. The
API and database are internal-only: the browser reaches them through the
nginx proxy on 8080, so ports 8000 and 5432 stay free for whatever else you
run.

### Debugging with direct API / database access

`curl` against the API or `psql` against TimescaleDB needs an opt-in
overlay, which binds them to **loopback only** on high ports chosen to stay
clear of typical dev servers:

```bash
docker compose -f docker-compose.yml -f docker-compose.debug.yml up -d

curl 127.0.0.1:18000/api/link                     # API
psql -h 127.0.0.1 -p 15432 -U postgres telemetry  # TimescaleDB
```

Override the ports with `API_DEBUG_PORT` / `DB_DEBUG_PORT` (see
`.env.example`). Without the overlay these ports are closed. You can always
reach the API through the normal proxy instead — `curl
localhost:8080/api/link` — and the database via
`docker compose exec timescaledb psql -U postgres -d telemetry`.

### Per-service resource limits

| Service | CPU | Memory | Published |
|---|---|---|---|
| `missioncontrol` (nginx + OpenMCT) | 0.25 | 128 M | **8080** |
| `api` (FastAPI) | 0.5 | 256 M | internal |
| `ingest` (UDP decode + limits) | 0.5 | 256 M | internal |
| `spacecraft` (simulator) | 0.25 | 128 M | internal |
| `timescaledb` | 1.0 | 1 G | internal |
| `redis` | 0.5 | 256 M | internal |

### Troubleshooting: Docker Desktop instability on Windows

If Docker Desktop crashes when several projects run at once, the usual cause
is that WSL2 has no memory cap — by default its VM can take ~50% of host RAM
plus every CPU, and it returns memory to Windows only lazily. Cap it by
creating `C:\Users\<you>\.wslconfig`:

```ini
[wsl2]
memory=8GB
processors=8
swap=2GB

[experimental]
autoMemoryReclaim=gradual
```

To apply it safely: quit Docker Desktop first (so databases checkpoint
cleanly), then `wsl --shutdown`, then reopen Docker Desktop. Container data
lives in named volumes on the WSL virtual disk and survives this.

## Testing

```bash
pytest tests/          # CCSDS codec, CRC vectors, limits, link monitoring
```

The `shared/` package is kept Python 3.9-compatible so the test suite runs
on a bare local interpreter, while the services themselves run 3.12 in
containers.
