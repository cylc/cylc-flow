Extending Workflow
------------------

.. cylc-scope:: flow.cylc[scheduling]

Sometimes we may run a workflow to :ref:`completion <workflow completion>`,
but subsequently wish to run it for a few more cycles.

With Cylc 7 this was often done by changing the `final cycle point` and
restarting the workflow. This approach worked, but was a little awkward.
It's possible with Cylc 8, but we would recommend moving away from this
pattern instead.

The recommended approach to this problem (Cylc 6+) is to use the
`stop after cycle point` rather than the `final cycle point`.

The `stop after cycle point` tells Cylc to **stop** after the workflow passes
the specified point, whereas the `final cycle point` tells Cylc that the
workflow **finishes** at the specified point.

When a workflow **finishes**, it is a little awkward to restart as you have to
tell Cylc which tasks to continue on from. The `stop after cycle point`
solution avoids this issue.


Example
^^^^^^^

.. admonition:: Get a copy of this example
   :class: hint

   .. code-block:: console

      $ cylc get-resources examples/extending-workflow/simple

This workflow will stop at the end of the ``2002`` cycle:

.. literalinclude:: simple/flow.cylc
   :language: cylc

After it has run and shut down, change the `stop after cycle point` to
the desired value and restart it. E.g:

.. code-block:: bash

   # install and run the workflow:
   cylc vip

   # then later edit "stop after cycle point" to "2004"

   # then reinstall and restart the workflow:
   cylc vr

The workflow will continue from where it left off and run until the end of the
``2004`` cycle. Because the workflow never hit the `final cycle point` it
never "finished" so no special steps are required to restart the workflow.

You can also set the `stop after cycle point` when you start the workflow:

.. code-block:: bash

   cylc play --stop-cycle-point=2020 myworkflow

Or change it at any point whilst the workflow is running:

.. code-block:: bash

   cylc stop myworkflow//2030  # change the stop after cycle point to 2030

.. note::

   If you set the `stop after cycle point` on the command line, this value will
   take precedence over the one in the workflow configuration. Use
   ``cylc play --stop-cycle-point=reload`` to restart the workflow using the
   `stop after cycle point` configured in the workflow configuration.


Running Tasks At The `stop after cycle point`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you have tasks that you want to run before the workflow shuts down at the
`stop after cycle point`, use the recurrence ``R1/<cycle-point>`` to schedule
them, e.g:

.. code-block:: cylc

   #!Jinja2

   {% set stop_cycle = '3000' %}

   [scheduling]
      initial cycle point = 2000
      stop after cycle point = {{ stop_cycle }}
      [[graph]]
         R1/{{ stop_cycle }} = """
            # these tasks will run *before* the workflow shuts down
            z => run_me => and_me
         """

When the workflow is subsequently restarted with a later
`stop after cycle point`, these tasks will be re-scheduled at the new
stop point.


.. cylc-scope::
