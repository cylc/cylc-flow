Inter-Workflow Triggering
=========================

.. admonition:: Get a copy of this example
   :class: hint

   .. code-block:: console

      $ cylc get-resources examples/inter-workflow-triggers

.. include:: README.rst

.. literalinclude:: upstream/flow.cylc
   :language: cylc
   :caption: Upstream Workflow

.. literalinclude:: downstream/flow.cylc
   :language: cylc
   :caption: Downstream Workflow

.. admonition:: Example - Decoupled workflows
   :class: hint

   This pattern is useful where you have workflows that you want to keep decoupled
   from one another, but still need to exchange data. E.G. in operational
   meteorology we might have a global model (covering the whole Earth) and a
   regional model (just covering a little bit of of) where the regional model
   obtains its boundary condition from the global model.
