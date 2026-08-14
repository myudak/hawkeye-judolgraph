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

The override selects `openai/gpt-5.6-luna` by default. Set the machine-specific exact browser
origin through `HAWKEYE_PUBLIC_DEMO_ORIGIN` in `.env`; the Compose file does not hard-code a domain.
The published port remains `127.0.0.1:8760`. Basic Auth remains optional; with both auth variables
empty, the demo is intentionally unauthenticated. Origin checks do not authenticate direct clients,
and this exception must not be described as production-ready.

Remote single-investigator access is supported through an SSH tunnel while the published port stays
on host loopback. See `docs/operations/DEPLOYMENT.md`.

## Optional collector-only VPN egress

`compose.vpn.yaml` routes the HAWK-EYE container through a Gluetun/OpenVPN sidecar without changing
the VPS host route. SSH and a host-managed Cloudflare Tunnel therefore continue to use the VPS IP.
The sidecar owns the loopback port publication because HAWK-EYE shares its network namespace.

Prepare an operator-supplied config before starting the overlay:

```bash
uv run python tools/deployment/prepare_openvpn_config.py \
  ca-free-15.protonvpn.udp.ovpn \
  data/vpn/ca-free-15.protonvpn.udp.ovpn
docker compose -f compose.yaml -f compose.vpn.yaml config --quiet
docker compose -f compose.yaml -f compose.vpn.yaml up -d --build
```

Keep the source `.ovpn` and `PROTON_OPENVPN_USER`/`PROTON_OPENVPN_PASSWORD` outside Git. The
preparation tool rejects private or unresolved endpoints, embedded client credentials, external
certificate files, routes, plugins, and scripts. It preserves inline CA/TLS material and chooses
one explicit public UDP endpoint so the runtime behavior is auditable.

`PROTON_OPENVPN_PORT` defaults to `51820` and overrides the first remote port in the supplied
configuration. For the checked Canada profile, operator-approved alternatives are `80`, `5060`,
`1194`, and `4569`. Keep `GLUETUN_LOG_LEVEL=warn` in normal operation so the settings summary
does not expose even a masked fragment of the OpenVPN password.

The overlay defaults to encrypted DNS-over-HTTPS through Cloudflare and Google. Gluetun's
malicious-domain blocklist is disabled for this investigator profile so it does not silently turn a
public target into a false DNS failure; HAWK-EYE still rejects private/non-public destinations and
keeps the browser read-only and bounded.

Gluetun is the only service receiving `NET_ADMIN` and `/dev/net/tun`. HAWK-EYE retains the base
non-root, read-only, capability-minimized boundary. If the VPN fails, Gluetun's firewall blocks
egress instead of falling back to the VPS route. A region restriction page remains a valid capture
outcome; this overlay does not authorize bypassing login, CAPTCHA, or access controls.
