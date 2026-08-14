from __future__ import annotations

import os
from pathlib import Path

import pytest
from tools.deployment.prepare_openvpn_config import (
    OpenVpnConfigError,
    prepare_openvpn_config,
    sanitize_openvpn_config,
)


def _config(*extra: str, remote: str = "remote 89.238.156.194 80") -> str:
    return "\n".join(
        [
            "client",
            "dev tun",
            "proto udp",
            remote,
            *extra,
            "auth-user-pass",
            "remote-cert-tls server",
            "<ca>",
            "test-ca",
            "</ca>",
            "<tls-crypt>",
            "test-static-key",
            "</tls-crypt>",
        ]
    )


def test_sanitizer_removes_scripts_and_selects_one_resolved_remote() -> None:
    result = sanitize_openvpn_config(
        _config(
            "remote 89.238.156.194 51820",
            "remote-random",
            "script-security 2",
            "up /etc/openvpn/update-resolv-conf",
            "down /etc/openvpn/update-resolv-conf",
        )
    )

    assert result.endpoint_ip == "89.238.156.194"
    assert result.endpoint_port == 80
    assert result.text.count("remote ") == 1
    assert "script-security" not in result.text
    assert "update-resolv-conf" not in result.text
    assert "<ca>\ntest-ca\n</ca>" in result.text
    assert "<tls-crypt>\ntest-static-key\n</tls-crypt>" in result.text


@pytest.mark.parametrize(
    ("config", "message"),
    [
        (_config(remote="remote vpn.example.test 1194"), "resolved public IP"),
        (_config(remote="remote 127.0.0.1 1194"), "public IP"),
        (_config("plugin malicious.so"), "plugin"),
        (_config("route 10.0.0.0 255.0.0.0"), "route"),
        (_config().replace("auth-user-pass", "auth-user-pass secrets.txt"), "credential file"),
        (_config().replace("<ca>\ntest-ca\n</ca>", "ca ca.crt"), "inline block"),
        (
            _config().replace("<tls-crypt>", "<key>").replace("</tls-crypt>", "</key>"),
            "credentials",
        ),
    ],
)
def test_sanitizer_rejects_unsafe_or_non_portable_configuration(config: str, message: str) -> None:
    with pytest.raises(OpenVpnConfigError, match=message):
        sanitize_openvpn_config(config)


def test_prepare_writes_private_runtime_copy(tmp_path: Path) -> None:
    source = tmp_path / "source.ovpn"
    destination = tmp_path / "runtime" / "custom.ovpn"
    source.write_text(_config(), encoding="utf-8")

    result = prepare_openvpn_config(source, destination)

    assert destination.read_text(encoding="utf-8") == result.text
    if os.name != "nt":
        assert destination.stat().st_mode & 0o077 == 0
