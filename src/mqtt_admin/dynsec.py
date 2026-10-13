"""Client for Mosquitto's dynamic-security plugin, which is driven by MQTT messages.

Commands go to $CONTROL/dynamic-security/v1 and answers come back on the /response
topic, matched by the correlationData we attach to each command.
"""
import json
import threading
import uuid

import paho.mqtt.client as mqtt

CMD_TOPIC = "$CONTROL/dynamic-security/v1"
RESP_TOPIC = CMD_TOPIC + "/response"


class DynSecError(Exception):
    pass


class DynSec:
    def __init__(self, host, port, username, password, tls=False, timeout=8.0):
        self.host, self.port, self.tls, self.timeout = host, port, tls, timeout
        self.username, self.password = username, password
        self._lock = threading.Lock()
        self._pending: dict[str, tuple[threading.Event, list]] = {}
        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self._client.username_pw_set(username, password)
        if tls:
            self._client.tls_set()
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message

    def start(self):
        self._client.connect_async(self.host, self.port, keepalive=30)
        self._client.loop_start()

    def stop(self):
        self._client.loop_stop()
        self._client.disconnect()

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        # Subscribing on every (re)connect keeps us listening after a broker restart.
        if not reason_code.is_failure:
            client.subscribe(RESP_TOPIC, qos=1)

    def _on_message(self, client, userdata, msg):
        try:
            replies = json.loads(msg.payload)["responses"]
        except (ValueError, KeyError):
            return
        for r in replies:
            waiter = self._pending.get(r.get("correlationData"))
            if waiter:
                waiter[1].append(r)
                waiter[0].set()

    def _command(self, name: str, **fields) -> dict:
        cid = uuid.uuid4().hex
        event, box = threading.Event(), []
        self._pending[cid] = (event, box)
        try:
            payload = json.dumps({"commands": [{"command": name, "correlationData": cid, **fields}]})
            info = self._client.publish(CMD_TOPIC, payload, qos=1)
            if not event.wait(self.timeout):
                raise DynSecError("The broker did not answer. Is it running and is dynsec enabled?")
            reply = box[0]
        finally:
            self._pending.pop(cid, None)
        if "error" in reply:
            raise DynSecError(reply["error"])
        return reply.get("data", {})

    # --- reads -------------------------------------------------------------
    def list_clients(self) -> list[dict]:
        return self._command("listClients", verbose=True).get("clients", [])

    def get_client(self, username: str) -> dict | None:
        try:
            return self._command("getClient", username=username).get("client")
        except DynSecError as e:
            if "not found" in str(e).lower():
                return None
            raise

    def list_roles(self) -> list[str]:
        return [r["rolename"] if isinstance(r, dict) else r
                for r in self._command("listRoles", verbose=False).get("roles", [])]

    # --- writes ------------------------------------------------------------
    def create_client(self, username, password, roles=(), textname=""):
        self._command("createClient", username=username, password=password,
                      textname=textname, roles=[{"rolename": r} for r in roles])

    def delete_client(self, username):
        self._command("deleteClient", username=username)

    def set_password(self, username, password):
        self._command("setClientPassword", username=username, password=password)

    def set_enabled(self, username, enabled: bool):
        self._command("enableClient" if enabled else "disableClient", username=username)

    def add_role(self, username, role):
        self._command("addClientRole", username=username, rolename=role)

    def remove_role(self, username, role):
        self._command("removeClientRole", username=username, rolename=role)

    # --- credentials -------------------------------------------------------
    def verify_login(self, username: str, password: str) -> bool:
        """dynsec has no 'check password' command, so prove it by connecting as the user."""
        done, ok = threading.Event(), []

        def on_connect(c, u, f, rc, p):
            ok.append(not rc.is_failure)
            done.set()

        probe = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        probe.username_pw_set(username, password)
        if self.tls:
            probe.tls_set()
        probe.on_connect = on_connect
        try:
            probe.connect(self.host, self.port, keepalive=10)
            probe.loop_start()
            done.wait(5)
        except OSError:
            return False
        finally:
            probe.loop_stop()
            try:
                probe.disconnect()
            except OSError:
                pass
        return bool(ok and ok[0])
