Suite Runtime Interface
=======================


Cylc suites are TCP servers which use the ZeroMQ protocol to communicate with
clients and jobs.

Cylc provides a Python client to communicate with this server
:py:class:`cylc.network.client.SuiteRuntimeClient`

.. code-block:: python

   >>> from cylc.network.client import SuiteRuntimeClient
   >>> client = SuiteRuntimeClient('my-suite')
   >>> client('ping_suite')
   True

Cylc also provides sub-command called ``cylc client`` which is a simple
wrapper of the Python client.

.. code-block:: console

   $ cylc client generic ping_suite -n
   true

The available "commands" or ("endpoints") are contained in
:py:class:`cylc.network.server.SuiteRuntimeServer` class.


Client
------

.. autoclass:: cylc.network.client.SuiteRuntimeClient


Server
------

.. autoclass:: cylc.network.server.SuiteRuntimeServer
   :members:
