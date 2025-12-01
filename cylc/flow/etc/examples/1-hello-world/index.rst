Hello World
-----------

.. admonition:: Get a copy of this example
   :class: hint

   .. code-block:: console

      $ cylc get-resources examples/1-hello-world ~/cylc-src/hello-world

In the time honoured tradition, this is the minimal Cylc workflow:

.. literalinclude:: flow.cylc
   :language: cylc

It writes the phrase "Hello World!" to standard output (captured to the
``job.out`` log file).

Run it with::

   $ cylc vip hello-world
