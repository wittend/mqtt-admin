Development
===========

Set up
------

Python 3.11 or later is required.

.. code-block:: bash

   python3 -m venv .venv
   .venv/bin/pip install -e '.[test]'

Run the tests
-------------

.. code-block:: bash

   .venv/bin/pytest

The tests use a fake broker that keeps accounts in memory. They cover password rules, sign-in limits, self-service password changes, the admin pages, and the CSV import, including line numbers in error messages.

.. note::

   Nothing in the test suite talks to a real Mosquitto broker. Verify dynsec behaviour on a broker before relying on a change. In particular, check the response format of ``listClients`` and ``getClient``, which the app assumes.

Build these docs
----------------

.. code-block:: bash

   .venv/bin/pip install -r docs/requirements.txt
   sphinx-build -b html docs docs/_build/html

Open ``docs/_build/html/index.html`` in a browser. Read the Docs builds the same pages from ``.readthedocs.yaml`` and treats warnings as errors.

Layout
------

``src/mqtt_admin/``
    The application: ``app.py`` (routes), ``dynsec.py`` (broker client), ``importer.py`` (CSV import), ``security.py`` (password rules and sign-in limits), ``config.py`` (settings), and ``templates/``.

``tests/``
    Pytest suites.

``mosquitto/``
    The dynsec configuration and the bootstrap script.

``deploy/``
    The systemd unit, the environment file example, and the Caddy site block.

Known gaps
----------

* No IPv6 path to the public name yet.
* Sign-in limits are per address, which is weaker for IPv6 clients.
* No audit log, e-mail password reset, or monitoring.
