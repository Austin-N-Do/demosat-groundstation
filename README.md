# DemoSat-1 Mission Telemetry System

End-to-end NASA-style real-time spacecraft telemetry system: a simulated
satellite downlinks CCSDS Space Packets over a lossy UDP "space link" into a
ground segment (decode, limit checking, Redis Streams bus, TimescaleDB
archive) visualized live in **NASA OpenMCT** — the open-source mission
control framework used at JPL and Ames.

> Work in progress — full architecture, quickstart, and screenshots land at
> the end of the build (Milestone M8).

## Quickstart

```bash
docker compose up --build
```

- Mission control (OpenMCT): http://localhost:8080
- Telemetry API: http://localhost:8000
