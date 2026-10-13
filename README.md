# mqtt-admin

A small web portal for Mosquitto users and passwords. Administrators add, disable, delete and reset users and assign roles. Ordinary users sign in with their MQTT credentials and change their own password from any browser, with no VPN or agent.

It talks to the broker through Mosquitto's dynamic-security plugin (dynsec), so it never touches files on the broker container and needs no access to the hypervisor.

Full documentation (installation, guides and reference) is in [`docs/`](docs/). It is built with Sphinx and the Furo theme for Read the Docs.

## How it fits

```
browser --https--> Caddy (<caddy-ip>) --http--> mqtt-admin LXC (<app-ip>):8080 --mqtt 1883--> Mosquitto (<broker-ip>)
tailnet browser --https--> Tailscale serve on Caddy --http--> mqtt-admin LXC :8080
```

- `/account` is public. It only changes the signed-in user's own password, after checking the current one.
- `/admin` is closed on the public name: Caddy returns 404 for it. The admin page is served only through Tailscale (`tailscale serve` on the Caddy container), so only devices on your tailnet can reach it. The app also checks the source address against its configured networks. Admins are users holding the `portal-admin` role, re-checked on every request, so revoking the role takes effect at once.
- Logins are rate-limited (5 failures per user and 20 per address in 15 minutes). Forms carry CSRF tokens and cookies are `SameSite=Strict`.

## Install

Step-by-step installation for another set of servers is in [`docs/install/`](docs/install/index.rst). In outline:

1. **Broker.** Install Mosquitto 2.x with `mosquitto-clients`. Copy `mosquitto/dynsec.conf` into `/etc/mosquitto/conf.d/` and set the plugin path. Remove the `password_file` and `acl_file` lines, then run `mosquitto/setup-dynsec.sh <admin-username>` before restarting the broker. It creates the `portal-svc` service account, the `portal-admin` role and your admin login.
2. **Existing users.** Hashes from `mosquitto_passwd` cannot be imported into dynsec, so accounts must be re-created. Create the roles your devices need, then import the users on the admin page from a CSV file (`username,password,textname,roles`, with roles separated by semicolons). Each row is checked before anything is created. Have everyone change their temporary password.
3. **App container.** Create a Debian LXC with a static address, then:
   ```
   useradd -r mqtt-admin; mkdir /opt/mqtt-admin   # copy this repo there
   python3 -m venv /opt/mqtt-admin/.venv && /opt/mqtt-admin/.venv/bin/pip install /opt/mqtt-admin
   cp deploy/mqtt-admin.env.example /etc/mqtt-admin.env   # fill in, chmod 600
   cp deploy/mqtt-admin.service /etc/systemd/system/ && systemctl enable --now mqtt-admin
   ```
   Set `--forwarded-allow-ips` in the unit file to the Caddy container's address.
4. **Caddy.** Replace the Caddyfile with the site block from `deploy/Caddyfile.snippet`, using your public hostname and the app container's address. Then install Tailscale on the Caddy container and serve the admin page to the tailnet:
   ```
   tailscale serve --bg --https=443 http://<app-ip>:8080
   ```
   Turn on HTTPS certificates in the Tailscale admin console first. Do not add a Caddy route for `/admin`; the site block already returns 404 for it.

   If the container has no TUN device, run Tailscale in userspace mode with `FLAGS="--tun=userspace-networking"` in `/etc/default/tailscaled`.

## Develop

```
python3 -m venv .venv && .venv/bin/pip install -e '.[test]' && .venv/bin/pytest
```

The tests use a fake broker. They do not talk to a real Mosquitto, so check dynsec behaviour on a real broker before relying on a change. The docs build with `sphinx-build -b html docs docs/_build/html`.
