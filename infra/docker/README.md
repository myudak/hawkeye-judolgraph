# Container boundary

The root `Dockerfile` and `compose.yaml` define the supported local container workflow. This
directory is reserved for container-only support material; it intentionally contains no evidence,
credentials, or generated browser state.

The runtime keeps Docker's default seccomp profile enabled and adds non-root execution, Chromium's
sandbox flag, dropped Linux capabilities, `no-new-privileges`, an init process, shared IPC, a
read-only root filesystem, and bounded tmpfs mounts. The published port is host loopback only.

This is not a production/public threat model. Do not change the bind address, add a reverse proxy,
or expose the container to a LAN/Internet without a separate authentication, authorization, TLS,
rate-limit, storage-isolation, and deployment review milestone.
