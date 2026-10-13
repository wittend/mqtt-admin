# Notes for the next session

Context a fresh session needs. The README covers install and design, and `docs/` has the full documentation. This file covers decisions and what is still open. Addresses, names and secrets are placeholders.

## Decisions made

- Mosquitto 2.x, run in an LXC on Proxmox. There is no fixed user count. No users existed on the broker at the time of deployment; the admin page's CSV import creates users in bulk.
- Caddy, the app and Mosquitto each run in their own container, with static addresses pinned in the router. The broker's TLS port (8883) is served by Mosquitto itself, and Caddy handles only the portal's web traffic.
- Users are managed through Mosquitto's dynamic-security plugin (dynsec), driven over MQTT by a small FastAPI app in its own container. PostgreSQL is not used, because dynsec is enough for the expected user count.
- Ordinary users may not be asked to install Tailscale or other agents. So `/account` (own password change) is public over HTTPS from Caddy. `/admin` is closed on that public name and served only on the tailnet, via `tailscale serve` on the Caddy container.
- Checking the source address at Caddy was not reliable, because the router can make some outside requests look like they come from its own LAN address. The tailnet route avoids relying on address checks.
- Admins are broker users holding the marker role `portal-admin`. There is no separate admin password store.
- The app verifies a user's password by connecting to the broker as that user, because dynsec has no check-password command.
- The Caddy container runs Tailscale in userspace mode, because it has no TUN device.

## Open items

1. Verify the dynsec response format for `listClients` and `getClient`. The code assumes `clients` and `client` keys with a `roles` list of `rolename` objects. The deployed system has exercised this path, but the tests use a fake broker.
2. Define the dynsec roles that publishers and dashboards need, with topic rules (`addRoleACL`). Until then, a new user has no topic access.
3. Back up `/var/lib/mosquitto/dynamic-security.json` and the app's environment file. The environment file holds secrets, so store the copy securely.
4. Restrict who can reach the admin page with Tailscale access rules, rather than relying on the tailnet as a whole.
5. Remove the old password file and the broker configuration backup once the dynsec setup has been confirmed on real devices.
6. Not built, deliberately: email password reset, audit log, and a monitoring or alerting setup. The disabled flag is shown only when the broker reports it.
7. The sign-in rate limit counts failures per address, which is weaker for IPv6 clients. Consider grouping IPv6 addresses by /64.
8. The public name has only an IPv4 address. Clients on IPv6-only networks cannot reach the portal until a public IPv6 address and matching DNS record are in place.
