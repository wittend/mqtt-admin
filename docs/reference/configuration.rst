Configuration
=============

The app reads its settings from environment variables. In the systemd service they come from ``/etc/mqtt-admin.env``, which must be readable by root only.

.. list-table::
   :header-rows: 1
   :widths: 25 20 55

   * - Variable
     - Default
     - Meaning
   * - ``MQTT_HOST``
     - built-in address
     - Broker address, as reached from the app container. Always set this to your broker's address.
   * - ``MQTT_PORT``
     - ``1883``
     - Broker port used by the app.
   * - ``MQTT_TLS``
     - ``0``
     - Set to ``1`` to connect to the broker over TLS.
   * - ``MQTT_SVC_USER``
     - ``portal-svc``
     - Service account the app uses. Hidden from the user list in the portal.
   * - ``MQTT_SVC_PASSWORD``
     - *(none)*
     - Password for ``MQTT_SVC_USER``. Required. The app refuses to start if it is empty.
   * - ``SESSION_SECRET``
     - *(none)*
     - Secret for signing session cookies. Required, at least 32 characters. Generate with ``python3 -c 'import secrets; print(secrets.token_urlsafe(48))'``.
   * - ``PORTAL_ADMIN_ROLE``
     - ``portal-admin``
     - Role that grants access to the admin page.
   * - ``ADMIN_NETS``
     - built-in list
     - Comma-separated networks allowed to reach ``/admin``. The built-in list covers the Tailscale range (``100.64.0.0/10``), loopback, and a LAN subnet. Always set it to your own tailnet range and LAN subnet.
   * - ``SECURE_COOKIES``
     - ``1``
     - Mark session cookies ``Secure``. Set to ``0`` only for plain-HTTP testing on a LAN.

The minimum password length is set in the code (``min_password_length``, default 12), not by an environment variable.

Proxy settings
--------------

The systemd unit runs uvicorn with ``--proxy-headers --forwarded-allow-ips=<caddy-ip>``. The app believes ``X-Forwarded-For`` only from that address. Change the value if Caddy's address changes.
