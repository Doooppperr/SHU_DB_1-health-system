"""Open a local TCP tunnel through an SSH host.

Configuration is read from environment variables so credentials do not need to
be stored in the repository:

    SSH_TUNNEL_HOST
    SSH_TUNNEL_USER
    SSH_TUNNEL_PASSWORD
    SSH_TUNNEL_LOCAL_PORT
    SSH_TUNNEL_REMOTE_HOST
    SSH_TUNNEL_REMOTE_PORT
"""

from __future__ import annotations

import os
import select
import socket
import socketserver
import sys
from dataclasses import dataclass

import paramiko


@dataclass(frozen=True)
class TunnelConfig:
    ssh_host: str
    ssh_port: int
    ssh_user: str
    ssh_password: str
    local_host: str
    local_port: int
    remote_host: str
    remote_port: int


class ForwardServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class TunnelHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        remote = (self.server.remote_host, self.server.remote_port)
        try:
            channel = self.server.transport.open_channel(
                "direct-tcpip",
                remote,
                self.request.getpeername(),
            )
        except Exception as exc:
            print(f"failed to open SSH channel: {exc}", file=sys.stderr, flush=True)
            return

        if channel is None:
            print("SSH channel was not opened", file=sys.stderr, flush=True)
            return

        try:
            while True:
                readable, _, _ = select.select([self.request, channel], [], [], 1)
                if self.request in readable:
                    data = self.request.recv(16384)
                    if not data:
                        break
                    channel.sendall(data)

                if channel in readable:
                    data = channel.recv(16384)
                    if not data:
                        break
                    self.request.sendall(data)
        finally:
            channel.close()
            self.request.close()


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SystemExit(f"{name} is required")
    return value


def load_config() -> TunnelConfig:
    return TunnelConfig(
        ssh_host=require_env("SSH_TUNNEL_HOST"),
        ssh_port=int(os.getenv("SSH_TUNNEL_PORT", "22")),
        ssh_user=require_env("SSH_TUNNEL_USER"),
        ssh_password=require_env("SSH_TUNNEL_PASSWORD"),
        local_host=os.getenv("SSH_TUNNEL_LOCAL_HOST", "127.0.0.1"),
        local_port=int(os.getenv("SSH_TUNNEL_LOCAL_PORT", "15432")),
        remote_host=require_env("SSH_TUNNEL_REMOTE_HOST"),
        remote_port=int(require_env("SSH_TUNNEL_REMOTE_PORT")),
    )


def connect_ssh(config: TunnelConfig) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=config.ssh_host,
        port=config.ssh_port,
        username=config.ssh_user,
        password=config.ssh_password,
        look_for_keys=False,
        allow_agent=False,
        timeout=15,
        banner_timeout=30,
        auth_timeout=30,
    )
    transport = client.get_transport()
    if transport is None:
        raise RuntimeError("SSH transport was not created")
    transport.set_keepalive(30)
    return client


def main() -> None:
    config = load_config()
    client = connect_ssh(config)
    transport = client.get_transport()
    assert transport is not None

    server = ForwardServer((config.local_host, config.local_port), TunnelHandler)
    server.transport = transport
    server.remote_host = config.remote_host
    server.remote_port = config.remote_port

    print(
        f"listening {config.local_host}:{config.local_port} -> "
        f"{config.remote_host}:{config.remote_port} via {config.ssh_host}",
        flush=True,
    )
    try:
        server.serve_forever()
    finally:
        server.server_close()
        client.close()


if __name__ == "__main__":
    main()
