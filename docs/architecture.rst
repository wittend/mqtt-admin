Architecture
============

.. code-block:: text

   Internet ──HTTPS──► Caddy ──HTTP──► portal app (port 8080) ──MQTT 1883──► Mosquitto + dynsec
                          ▲
   Tailnet ──HTTPS──► Tailscale serve on Caddy ──HTTP──► portal app   (admin page only)

Components
----------

.. list-table::
   :header-rows: 1
   :widths: 20 30 50

   * - Component
     - Where it runs
     - Role
   * - Caddy
     - Its own container or host, with a public address
     - Terminates HTTPS for the portal's public name, sets security headers, forwards requests to the app. The broker's own TLS port (8883) is not handled by Caddy.
   * - Portal app
     - Its own container, port 8080
     - A FastAPI application run by uvicorn under systemd. Serves the pages and talks to the broker.
   * - Mosquitto
     - Its own container
     - MQTT 2.x with the dynamic-security plugin. Holds the accounts, roles and topic rules.
   * - Tailscale
     - On the Caddy container
     - Gives administrators a private route to the admin page. Its sign-in and device approval decide who can reach it.

Public and private routes
-------------------------

.. list-table::
   :header-rows: 1
   :widths: 35 15 50

   * - Path
     - Public name
     - Notes
   * - ``/account``, ``/account/login``, ``/account/password``, ``/account/logout``
     - Open
     - Ordinary users. Rate-limited.
   * - ``/admin/*``
     - Returns 404
     - Administrators only, through the tailnet.

Addresses and DNS
-----------------

* The public name has a DNS record that points at the router's public address. Set it to *DNS only*. A proxying service in front of Caddy would stop Caddy from obtaining its certificate.
* The router forwards TCP 80 and 443 to Caddy. Port 80 is used for redirects and certificate checks, and port 443 for HTTPS.
* Pin every container's address, both in its own network settings and in the router. The app trusts forwarded client addresses only from Caddy's address, so a changed Caddy address breaks client detection.

IPv4 and IPv6
-------------

The public name currently has only an IPv4 address. Clients on IPv6-only networks cannot reach the portal, and the Caddy container has no public IPv6 address. Dual-stack clients and tailnet clients work normally.
