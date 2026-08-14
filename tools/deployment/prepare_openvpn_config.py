"""Validate and sanitize one operator-supplied OpenVPN client configuration."""

from __future__ import annotations

import argparse
import ipaddress
import os
import shlex
import tempfile
from dataclasses import dataclass
from pathlib import Path

MAX_CONFIG_BYTES = 256 * 1024
ALLOWED_INLINE_BLOCKS = {"ca", "tls-auth", "tls-crypt", "tls-crypt-v2"}
FORBIDDEN_INLINE_BLOCKS = {"cert", "key", "pkcs12"}
REMOVED_DIRECTIVES = {
    "down",
    "down-pre",
    "ipchange",
    "remote-random",
    "route-up",
    "script-security",
    "up",
    "up-delay",
    "up-restart",
}
FORBIDDEN_DIRECTIVES = {
    "auth-user-pass-verify",
    "client-connect",
    "client-disconnect",
    "learn-address",
    "plugin",
    "route",
    "route-ipv6",
    "tls-verify",
}
EXTERNAL_FILE_DIRECTIVES = {
    "ca",
    "cert",
    "crl-verify",
    "dh",
    "extra-certs",
    "key",
    "pkcs12",
    "tls-auth",
    "tls-crypt",
    "tls-crypt-v2",
}


class OpenVpnConfigError(ValueError):
    """Raised when a source config is unsafe or incompatible with the VPN sidecar."""


@dataclass(frozen=True)
class SanitizedOpenVpnConfig:
    text: str
    endpoint_ip: str
    endpoint_port: int


def _tokens(line: str, *, line_number: int) -> list[str]:
    try:
        return shlex.split(line, comments=False, posix=True)
    except ValueError as error:
        raise OpenVpnConfigError(f"invalid quoting on line {line_number}") from error


def _validate_remote(tokens: list[str], *, line_number: int) -> tuple[str, int]:
    if len(tokens) not in {3, 4}:
        raise OpenVpnConfigError(f"remote on line {line_number} must contain an IP and port")
    try:
        address = ipaddress.ip_address(tokens[1])
    except ValueError as error:
        raise OpenVpnConfigError(
            f"remote on line {line_number} must use a resolved public IP"
        ) from error
    if not address.is_global:
        raise OpenVpnConfigError(f"remote on line {line_number} must use a public IP")
    try:
        port = int(tokens[2])
    except ValueError as error:
        raise OpenVpnConfigError(f"remote on line {line_number} has an invalid port") from error
    if not 1 <= port <= 65535:
        raise OpenVpnConfigError(f"remote on line {line_number} has an invalid port")
    if len(tokens) == 4 and tokens[3].lower() not in {"udp", "udp4"}:
        raise OpenVpnConfigError(f"remote on line {line_number} must use UDP")
    return str(address), port


def sanitize_openvpn_config(source: str) -> SanitizedOpenVpnConfig:
    """Return a Gluetun-compatible config without scripts, external files, or fallback routes."""

    if "\x00" in source:
        raise OpenVpnConfigError("config contains a NUL byte")

    output = ["# Sanitized for the HAWK-EYE Gluetun sidecar; do not edit in place."]
    block: str | None = None
    seen_blocks: set[str] = set()
    seen_directives: set[str] = set()
    selected_remote: tuple[str, int] | None = None

    for line_number, raw_line in enumerate(source.splitlines(), start=1):
        line = raw_line.strip()
        if block is not None:
            output.append(raw_line)
            if line.lower() == f"</{block}>":
                block = None
            continue
        if not line or line.startswith(("#", ";")):
            continue
        if line.startswith("<") and line.endswith(">"):
            tag = line[1:-1].strip().lower()
            if tag.startswith("/"):
                raise OpenVpnConfigError(f"unexpected closing block on line {line_number}")
            if tag in FORBIDDEN_INLINE_BLOCKS:
                raise OpenVpnConfigError(f"inline {tag} credentials are not allowed")
            if tag not in ALLOWED_INLINE_BLOCKS:
                raise OpenVpnConfigError(f"unsupported inline block {tag!r}")
            block = tag
            seen_blocks.add(tag)
            output.append(f"<{tag}>")
            continue

        tokens = _tokens(line, line_number=line_number)
        if not tokens:
            continue
        directive = tokens[0].lower()
        if directive in REMOVED_DIRECTIVES:
            continue
        if directive in FORBIDDEN_DIRECTIVES:
            raise OpenVpnConfigError(f"directive {directive!r} is not allowed")
        if directive in EXTERNAL_FILE_DIRECTIVES:
            raise OpenVpnConfigError(f"directive {directive!r} must use an inline block")
        if directive == "auth-user-pass" and len(tokens) != 1:
            raise OpenVpnConfigError("auth-user-pass must not reference a credential file")
        if directive == "remote":
            candidate = _validate_remote(tokens, line_number=line_number)
            if selected_remote is None:
                selected_remote = candidate
                output.append(f"remote {candidate[0]} {candidate[1]}")
            continue
        if directive == "proto" and tokens[1:] not in (["udp"], ["udp4"]):
            raise OpenVpnConfigError("only UDP OpenVPN configurations are supported")
        if directive == "dev" and tokens[1:] != ["tun"]:
            raise OpenVpnConfigError("OpenVPN config must use dev tun")
        seen_directives.add(directive)
        output.append(line)

    if block is not None:
        raise OpenVpnConfigError(f"unterminated inline block {block!r}")
    required = {"auth-user-pass", "client", "dev", "proto", "remote-cert-tls"}
    missing = sorted(required - seen_directives)
    if missing:
        raise OpenVpnConfigError(f"missing required directives: {', '.join(missing)}")
    if selected_remote is None:
        raise OpenVpnConfigError("config does not contain a usable remote")
    if "ca" not in seen_blocks:
        raise OpenVpnConfigError("config must contain an inline CA certificate")
    if not seen_blocks.intersection({"tls-auth", "tls-crypt", "tls-crypt-v2"}):
        raise OpenVpnConfigError("config must contain inline TLS key material")

    return SanitizedOpenVpnConfig(
        text="\n".join(output) + "\n",
        endpoint_ip=selected_remote[0],
        endpoint_port=selected_remote[1],
    )


def prepare_openvpn_config(source: Path, destination: Path) -> SanitizedOpenVpnConfig:
    """Read, validate, and atomically write an owner-readable runtime configuration."""

    if source.stat().st_size > MAX_CONFIG_BYTES:
        raise OpenVpnConfigError("config exceeds the 256 KiB limit")
    sanitized = sanitize_openvpn_config(source.read_text(encoding="utf-8"))
    destination.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(sanitized.text)
        temporary.chmod(0o600)
        temporary.replace(destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return sanitized


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    arguments = parser.parse_args()
    sanitized = prepare_openvpn_config(arguments.source, arguments.destination)
    print(
        f"Prepared {arguments.destination} using UDP endpoint "
        f"{sanitized.endpoint_ip}:{sanitized.endpoint_port}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
