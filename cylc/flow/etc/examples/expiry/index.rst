.. _examples.expiry:

Expiring Tasks / Cycles
-----------------------

Cylc is often used to write workflows which monitor real-world events.

For example, this workflow will run the task ``foo`` every day at 00:00am:

.. code-block:: cylc

   [scheduling]
      initial cycle point = previous(T00)
      [[graph]]
          P1D = """
              @wall_clock => foo
          """

Sometimes such workflows might get behind, e.g. due to failures or slow task
execution. In this situation, it might be necessary to skip a few tasks in
order for the workflow to catch up with the real-world time.

Cylc has a concept called :ref:`expiry <ClockExpireTasks>` which allows tasks
to be automatcially "expired" if they are running behind schedule. The expiry
can be configred as an offset from the cycle time.

.. seealso::

   :ref:`ClockExpireTasks`.


Example 1: Skip a whole cycle of tasks
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If the workflow gets behind, skip whole cycles of tasks until it catches up.

.. admonition:: Get a copy of this example
   :class: hint

   .. code-block:: console

      $ cylc get-resources examples/expiry/one

.. literalinclude:: one/flow.cylc
   :language: cylc


Example 2: Skip the remainder of a cycle of tasks
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If the workflow gets behind, skip the remainder of the tasks in the cycle,
then skip whole cycles of tasks until it catches up.

.. admonition:: Get a copy of this example
   :class: hint

   .. code-block:: console

      $ cylc get-resources examples/expiry/two

.. literalinclude:: two/flow.cylc
   :language: cylc


Example 3: Skip selected tasks in a cycle
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If the workflow gets behind, turn off selected tasks to allow it to catch up
more quickly.

.. admonition:: Get a copy of this example
   :class: hint

   .. code-block:: console

      $ cylc get-resources examples/expiry/three

.. literalinclude:: three/flow.cylc
   :language: cylc
