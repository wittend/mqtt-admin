import ipaddress
import os
from dataclasses import dataclass, field


def _nets(raw: str):
    return [ipaddress.ip_network(n.strip()) for n in raw.split(",") if n.strip()]


@dataclass
class Settings:
    # Where the broker is reached from this container, not the public hostname.
    mqtt_host: str = "127.0.0.1"
    mqtt_port: int = 1883
    mqtt_tls: bool = False
    # Service account holding the dynsec "admin" role. Never shown to users.
    svc_user: str = "portal-svc"
    svc_password: str = ""
    # People allowed into /admin carry this role. It grants nothing on the broker.
    admin_role: str = "portal-admin"
    session_secret: str = ""
    secure_cookies: bool = True
    # /admin is refused from anywhere else, even if the proxy misroutes it.
    # Set ADMIN_NETS to your own tailnet range and LAN subnet. Only the Tailscale range and loopback are built in.
    admin_nets: list = field(default_factory=lambda: _nets("100.64.0.0/10,127.0.0.1/32"))
    min_password_length: int = 12

    @classmethod
    def from_env(cls) -> "Settings":
        e = os.environ
        s = cls(
            mqtt_host=e.get("MQTT_HOST", cls.mqtt_host),
            mqtt_port=int(e.get("MQTT_PORT", cls.mqtt_port)),
            mqtt_tls=e.get("MQTT_TLS", "0") == "1",
            svc_user=e.get("MQTT_SVC_USER", cls.svc_user),
            svc_password=e.get("MQTT_SVC_PASSWORD", ""),
            admin_role=e.get("PORTAL_ADMIN_ROLE", cls.admin_role),
            session_secret=e.get("SESSION_SECRET", ""),
            secure_cookies=e.get("SECURE_COOKIES", "1") == "1",
        )
        if e.get("ADMIN_NETS"):
            s.admin_nets = _nets(e["ADMIN_NETS"])
        if not s.svc_password or len(s.session_secret) < 32:
            raise SystemExit(
                "Set MQTT_SVC_PASSWORD and a SESSION_SECRET of at least 32 characters "
                "(see deploy/mqtt-admin.env.example)."
            )
        return s
