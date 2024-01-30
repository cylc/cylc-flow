Extending Workflow
==================

.. cylc-scope:: flow.cylc[scheduling]

Sometimes we may run a workflow to completion, but subsequently wish to
run it for a few more cycles.

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


Simple Example
--------------

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


Complex Example
---------------

.. admonition:: Get a copy of this example
   :class: hint

   .. code-block:: console

      $ cylc get-resources examples/extending-workflow/complex

Sometimes we may want to run some tasks at the `final cycle point` or in the
cycles leading up to the `final cycle point`. For example you might have some
analysis or housekeeping tasks to run at the end of the workflow.

The following recurrence formats come in handy for such cases:

.. code-block:: sub

   # run once in the "2000" cycle
   R1/2000  # 2000

   # run every year three times ending in 2000
   R3/P1Y/2000  # 1998, 1999, 2000

For more information see :ref:`user_guide.cycling_format_4`.

This example uses Jinja2 to template the cycling expressions above to schedule
tasks to run at, and in the run up to, the `stop after cycle point`:

.. literalinclude:: complex/flow.cylc
   :language: cylc

.. digraph:: Example
   :align: center

   size = "10, 10"

   subgraph cluster_1 {
      label = "Spin Up (first 3 cycles)"
      style = "dashed"

      build_2000 [label="build\n2000"]
      install_2000 [label="install\n2000"]
      initial_conditions_2000 [label="initial_conditions\n2000"]
      initial_conditions_2001 [label="initial_conditions\n2001"]
      initial_conditions_2002 [label="initial_conditions\n2002"]
      run_model_2000 [label="run_model\n2000"]
      run_model_2001 [label="run_model\n2001"]
      run_model_2002 [label="run_model\n2002"]

      build_2000 -> install_2000 -> run_model_2000
      run_model_2000 -> run_model_2001 -> run_model_2002
      initial_conditions_2000 -> run_model_2000
      initial_conditions_2001 -> run_model_2001
      initial_conditions_2002 -> run_model_2002
   }

   subgraph cluster_2 {
      label = "Main section"
      style = "dashed"

      run_model_2003 [label="run_model\n2003"]
      run_model_2004 [label="run_model\n2004"]
      run_model_2005 [label="run_model\n2005"]
      run_model_2006 [label="run_model\n2006"]
      run_model_2007 [label="run_model\n2007"]

      run_model_2002 -> run_model_2003 -> run_model_2004 -> run_model_2005
      run_model_2005 -> run_model_2006 -> run_model_2007
   }

   subgraph cluster_3 {
      label = "Spin down (last 3 cycles)"
      style = "dashed"

      run_model_2008 [label="run_model\n2008"]
      run_model_2009 [label="run_model\n2009"]
      run_model_2010 [label="run_model\n2010"]
      process_2008 [label="process\n2008"]
      process_2009 [label="process\n2009"]
      process_2010 [label="process\n2010"]
      analyse_2010 [label="analyse\n2010"]
      plot_2010 [label="plot\n2010"]

      run_model_2007 -> run_model_2008 -> run_model_2009 -> run_model_2010
      run_model_2008 -> process_2008
      run_model_2009 -> process_2009
      run_model_2010 -> process_2010
      process_2008 -> process_2009
      process_2009 -> process_2010
      process_2010 -> analyse_2010 -> plot_2010
   }

To run the workflow:

.. code-block:: bash

   # install and run the workflow:
   cylc vip

   # then reinstall and restart the workflow extending the stop cycle:
   cylc vr -s stop_cycle=2020


.. cylc-scope::
