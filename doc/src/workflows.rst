.. _Workflows For Cycling Systems:

Workflows For Cycling Systems
=============================

A model run and associated processing may need to be cycled for the following
reasons:

- In real time forecasting systems, a new forecast may be initiated
  at regular intervals when new real time data comes in.
- It may be convenient (or necessary, e.g. due to batch scheduler
  queue limits) to split single long model runs into many smaller chunks,
  each with associated pre- and post-processing workflows.

Cylc provides two ways of constructing workflows for cycling systems:
*cycling workflows* and *parameterized tasks*.


.. _Cycling Workflows:

Cycling Workflows
-----------------

This is cylc's classic cycling mode as described in the Introduction. Each
instance of a cycling job is represented by a new instance of *the same task*,
with a new cycle point. The suite configuration defines patterns for
extending the workflow on the fly, so it can keep running indefinitely if
necessary. For example, to cycle ``model.exe`` on a monthly sequence we
could define a single task ``model``, an initial cycle point, and a
monthly sequence. Cylc then generates the date-time sequence and creates a new
task instance for each cycle point as it comes up. Workflow dependencies are
defined generically with respect to the "current cycle point" of the tasks
involved.

This is the only sensible way to run very large suites or operational suites
that need to continue cycling indefinitely. The cycling is configured with
standards-based ISO 8601 date-time *recurrence expressions*. Multiple
cycling sequences can be used at once in the same suite. See
:ref:`ConfiguringScheduling`.


.. _Parameterized-Tasks-as-a-Proxy-for-Cycling:

Parameterized Tasks as a Proxy for Cycling
------------------------------------------

It is also possible to run cycling jobs with a pre-defined static workflow in
which each instance of a cycling job is represented by *a different task*:
as far as the abstract workflow is concerned there is no cycling. The sequence
of tasks can be constructed efficiently, however, using cylc's built-in suite
parameters (:ref:`Parameterized Cycling`) or explicit Jinja2 loops
(:ref:`Jinja`).

For example, to run ``model.exe`` 12 times on a monthly cycle we could
loop over an integer parameter ``R = 0, 1, 2, ..., 11`` to define tasks
``model-R0, model-R1, model-R2, ...model-R11``, and the parameter
values could be multiplied by the interval ``P1M`` (one month) to get
the start point for the corresponding model run.

This method is only good for smaller workflows of finite duration because every
single task has to be mapped out in advance, and cylc has to be aware of all of
them throughout the entire run. Additionally Cylc's *cycling workflow*
capabilities (above) are more powerful, more flexible, and generally easier to
use (Cylc will generate the cycle point date-times for you, for instance), so
that is the recommended way to drive most cycling systems.

The primary use for parameterized tasks in cylc is to generate ensembles and
other groups of related tasks at the same cycle point, not as a proxy for
cycling.


Mixed Cycling Workflows
-----------------------

For completeness we note that parameterized cycling can be used within a
cycling workflow. For example, in a daily cycling workflow long (daily)
model runs could be split into four shorter runs by parameterized cycling.
A simpler six-hourly cycling workflow should be considered first, however.
