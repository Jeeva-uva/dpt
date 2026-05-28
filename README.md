# dept-track-multi

Spin up three isolated [Dependency-Track](https://dependencytrack.org/) instances (one per
"department"/company), generate a CycloneDX SBOM for each demo project, and upload them — all
with one script.

| Dept | Company | API | UI | Projects | Stack |
|---|---|---|---|---|---|
| acme | Acme Corp | `:8081` | `:8091` | express, juice-shop | Node.js |
| beta | Beta Industries | `:8082` | `:8092` | fastapi, flask | Python |
| gamma | Gamma Solutions | `:8083` | `:8093` | guava, spring-petclinic | Java |

## Requirements

- Linux host with **Docker 24+** + the compose plugin, plus `git` and `python3`
- **~16 GB RAM** (three Dependency-Track apiservers are JVM-based and memory-hungry;
  lower `-Xmx2g` in `docker-compose.yml` or run fewer departments on smaller hosts)
- Open TCP ports `8081-8083` and `8091-8093`

## Quick start

```bash
git clone <this-repo-url> dept-track-multi
cd dept-track-multi
chmod +x run.sh gen_sboms.sh
SERVER_HOST=<public-ip-of-this-server> ./run.sh
```

Use the IP/hostname your browser will reach — **not** `localhost`, or the UI can't talk to
the API. Set the admin password with `DT_ADMIN_PASSWORD=...` (default `ChangeMe123!`).

`run.sh` then: starts the 6 containers → generates SBOMs → waits for each API → creates the
projects → uploads. First run pulls the ~16 GB cdxgen image, so it's slow.

When it finishes, open the dashboards (login `admin` / your password):
`http://<ip>:8091` (acme), `:8092` (beta), `:8093` (gamma). Minted API keys land in
`api_keys.json`.

## Useful flags

```bash
SKIP_SBOMS=1 ./run.sh   # don't regenerate SBOMs (expects ./sboms/*.cdx.json to exist)
SKIP_UP=1    ./run.sh   # don't (re)start containers, just upload
```

## Files

| File | Purpose |
|---|---|
| `run.sh` | One-shot orchestrator (start → SBOMs → upload) |
| `config.py` | Department/project topology — the only file you edit to change what's deployed |
| `docker-compose.yml` | The 6 containers (apiserver + frontend per dept) |
| `gen_sboms.sh` | Clones the demo repos and runs cdxgen to produce `<dept>-<project>.cdx.json` |
| `setup_and_upload.py` | Authenticates, creates projects, uploads SBOMs, writes `api_keys.json` |

## Teardown

```bash
docker compose down       # stop, keep data
docker compose down -v    # stop and wipe all Dependency-Track data
```
