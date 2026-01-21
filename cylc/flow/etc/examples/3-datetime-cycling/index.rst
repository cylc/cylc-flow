Datetime Cycling
================

.. n.b: get-resources will strip the number and install to ~/cylc-src

.. admonition:: Get a copy of this example
   :class: hint

   .. code-block:: console

      $ cylc get-resources examples/3-datetime-cycling

.. literalinclude:: flow.cylc
   :language: cylc

Run it with::

   $ cylc vip datetime-cycling
