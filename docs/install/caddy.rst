3. Caddy (public HTTPS)
=======================

Caddy terminates HTTPS for ``<portal-host>`` and forwards requests to the app.

Install and replace the config
------------------------------

Install Caddy from its official packages. The stock configuration serves only a default page on port 80, so **replace** the whole ``/etc/caddy/Caddyfile`` rather than adding to it.

The site block in ``deploy/Caddyfile.snippet`` is the reference. In outline:

.. code-block:: text

   <portal-host> {
       encode zstd gzip

       request_body {
           max_size 512KB
       }

       @admin path /admin /admin/*
       handle @admin {
           respond 404
       }

       handle {
           reverse_proxy <app-ip>:8080
       }

       header {
           Strict-Transport-Security "max-age=31536000"
           X-Content-Type-Options nosniff
       }
   }

``request_body`` stops oversized uploads before the app reads them. The CSV import is capped at 256 KB. Every other form is short.

``/admin`` returns 404 on this public name. The admin page is served only through Tailscale (:doc:`tailnet`).

Validate and load
-----------------

.. code-block:: bash

   caddy validate --config /etc/caddy/Caddyfile
   systemctl reload caddy

Certificates
------------

Caddy obtains a certificate for ``<portal-host>`` automatically the first time it is needed. For that to work:

* the public DNS record for ``<portal-host>`` must point at your public address
* the router must forward TCP 80 and 443 to ``<caddy-ip>``

Set the DNS record to *DNS only*. A proxying service in front of Caddy would stop it getting the certificate.

Broker port
-----------

Caddy handles only the portal's web traffic. The broker serves its own TLS on port 8883, using the certificate in its listener configuration. If you publish the broker, forward port 8883 on the router directly to ``<broker-ip>``.
