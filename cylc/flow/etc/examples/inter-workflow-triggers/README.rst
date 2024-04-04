This example shows how one workflow can "trigger off" of tasks in another
workflow.

In this example, there are two workflows:

* "upstream" writes a file.
* "downstream" reads this file.

Run both workflows simultaneously to see this in action:

.. code-block:: console

   $ cylc vip inter-workflow-triggers/upstream
   $ cylc vip inter-workflow-triggers/downstream
