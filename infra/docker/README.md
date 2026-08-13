# Container boundary

The root `Dockerfile` and `compose.yaml` define the supported local container workflow. This
directory is reserved for container-only support material; it intentionally contains no evidence,
credentials, or generated browser state.

The runtime keeps a default-deny Docker-compatible seccomp boundary and adds non-root execution,
Chromium's sandbox flag, dropped Linux capabilities, `no-new-privileges`, an init process, shared
IPC, a read-only root filesystem, and bounded tmpfs mounts. The published port is host loopback
only.

`seccomp_profile.json` is the profile shipped by Microsoft Playwright tag `v1.50.0`: Docker's
default-deny profile plus the `clone`, `setns`, and `unshare` user-namespace permissions required by
the Chromium sandbox. It is pinned alongside the matching Python package and Docker image; do not
replace it with `seccomp=unconfined` or disable the browser sandbox.

Compose drops every Linux capability and adds back only `SYS_CHROOT`, which Chromium uses inside
its sandbox. The container is not privileged and does not receive `SYS_ADMIN`.

This is not a production/public threat model. Do not change the bind address, add a reverse proxy,
or expose the container to a LAN/Internet without a separate authentication, authorization, TLS,
rate-limit, storage-isolation, and deployment review milestone.

Run the complete isolated acceptance gate from the repository root:

```powershell
pnpm verify:docker
```

For the owner-authorized temporary OpenRouter demo, keep `OPENROUTER_APIKEY` in the ignored root
`.env` file and start the checked-in override:

```powershell
docker compose -f compose.yaml -f compose.openrouter.yaml up -d --build
```

The override selects `openai/gpt-5.6-luna` by default and enables only the exact browser origin
`https://hawkeye.myudak.com`. The published port remains `127.0.0.1:8760`. Basic Auth remains
optional; with both auth variables empty, the demo is intentionally unauthenticated. Origin checks
do not authenticate direct clients, and this exception must not be described as production-ready.

Remote single-investigator access is supported through an SSH tunnel while the published port stays
on host loopback. See `docs/operations/DEPLOYMENT.md`.
