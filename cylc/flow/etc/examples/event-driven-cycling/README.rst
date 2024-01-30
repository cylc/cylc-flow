Cylc is good at orchestrating tasks to a schedule, e.g:

* ``PT1H`` - every hour
* ``P1D`` - every day
* ``P1M`` - every month
* ``PT1H ! (T00, T12)`` - every hour, except midnight and midday.

But sometimes the things you want to run don't have a schedule.

This example uses ``cylc ext-trigger`` to establish a pattern where Cylc waits
for an external signal and starts a new cycle every time a signal is received.

The signal can carry data using the ext-trigger ID, this example sets the ID
as a file path containing some data that we want to make available to the tasks
that run in the cycle it triggers.

To use this example, first start the workflow as normal::

   cylc vip event-driven-cycling

Then, when you're ready, kick off a new cycle, specifying any 
environment variables you want to configure this cycle with::

   ./bin/trigger <workflow-id> WORLD=earth

Replacing ``<workflow-id>`` with the ID you installed this workflow as.

.. admonition:: Example - CI/CD
   :class: hint

   This pattern is good for CI/CD type workflows where you're waiting on
   external events. This pattern is especially powerful when used with
   sub-workflows where it provides a solution to two-dimensional cycling
   problems.

.. admonition:: Example - Polar satellite data processing
   :class: hint

   Polar satellites pass overhead at irregular intervals. This makes it tricky
   to schedule data processing because you don't know when the satellite will
   pass over the receiver station. With the event driven cycling approach you
   could start a new cycle every time data arrives.

.. note::

   * The number of parallel cycles can be adjusted by changing the
     :cylc:conf:`[scheduling]runahead limit`.
   * To avoid hitting the runahead limit, ensure that failures are handled in
     the graph.
