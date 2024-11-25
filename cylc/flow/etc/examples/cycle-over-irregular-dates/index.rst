Irregular Cycling
-----------------

We typically schedule tasks on regular intervals, e.g. ``P1D`` (every day) or
``PT1H`` (every hour), however, sometimes our intervals are irregular.

:ref:`user_guide.scheduling.exclusions` can be used to "subtract" dates or
entire recurrences e.g:

``PT1H!PT6H``
   Every hour, except every six hours.
``PT1H!(T00, T12)``
   Every hour, except at 00:00 and 12:00.

However, sometimes we want to schedule tasks on completely irregular intervals
or at arbitrary dates. E.g, when working on case studies, you might have a list
or range of arbitrary dates to work with.


.. rubric:: Simple Example

.. admonition:: Get a copy of this example
   :class: hint

   .. code-block:: console

      $ cylc get-resources examples/cycle-over-irregular-dates/simple

This example uses :ref:`Jinja` to define the list of dates and write out a
scheduling section for each.

.. literalinclude:: simple/flow.cylc
   :language: cylc

.. tip::

   You can see the result of this Jinja2 code by running the ``cylc view -p``
   command.


.. rubric:: Example with inter-cycle dependencies

.. admonition:: Get a copy of this example
   :class: hint

   .. code-block:: console

      $ cylc get-resources examples/cycle-over-irregular-dates/inter-dependent

.. _Jinja2 loop variable: https://jinja.palletsprojects.com/en/3.0.x/templates/#list-of-control-structures

If you have dependencies between the cycles, you can make this work by using the
`Jinja2 loop variable`_.

For example, the previous iteration of the ``{% for date in DATES %}`` loop is
available as ``loop.previtem`` and the next as ``loop.nextitem``.

If you need to make the tasks which cycle on *irregular* intervals dependent on
tasks which cycle on *regular* intervals, then you might find the
:py:func:`strftime <cylc.flow.jinja.filters.strftime.strftime>` function
helpful as a way of determining the nearest matching cycle.

.. literalinclude:: inter-dependent/flow.cylc
   :language: cylc

You can see how the cycles are linked together using the ``cylc graph``
command:

.. NOTE: use "cylc graph . -o foo.dot --cycles 2000 2001" to generate this code

.. digraph:: Example
   :align: center

   size = "7,15"

   graph [fontname="sans" fontsize="25"]
   node [fontname="sans"]
 
   subgraph "cluster_20000101T0000Z" { 
     label="20000101T0000Z"
     style="dashed"
     "20000101T0000Z/install" [label="install\n20000101T0000Z"]
     "20000101T0000Z/prep" [label="prep\n20000101T0000Z"]
   }
 
   subgraph "cluster_20000105T0600Z" { 
     label="20000105T0600Z"
     style="dashed"
     "20000105T0600Z/plot" [label="plot\n20000105T0600Z"]
     "20000105T0600Z/run_model" [label="run_model\n20000105T0600Z"]
   }
 
   subgraph "cluster_20000305T1200Z" { 
     label="20000305T1200Z"
     style="dashed"
     "20000305T1200Z/plot" [label="plot\n20000305T1200Z"]
     "20000305T1200Z/run_model" [label="run_model\n20000305T1200Z"]
   }
 
   subgraph "cluster_20000528T1336Z" { 
     label="20000528T1336Z"
     style="dashed"
     "20000528T1336Z/plot" [label="plot\n20000528T1336Z"]
     "20000528T1336Z/run_model" [label="run_model\n20000528T1336Z"]
   }
 
   subgraph "cluster_20010101T0000Z" { 
     label="20010101T0000Z"
     style="dashed"
     "20010101T0000Z/prep" [label="prep\n20010101T0000Z"]
   }
 
   subgraph "cluster_20010105T2324Z" { 
     label="20010105T2324Z"
     style="dashed"
     "20010105T2324Z/plot" [label="plot\n20010105T2324Z"]
     "20010105T2324Z/run_model" [label="run_model\n20010105T2324Z"]
   }
 
   "20000101T0000Z/install" -> "20000101T0000Z/prep"
   "20000101T0000Z/install" -> "20010101T0000Z/prep"
   "20000101T0000Z/prep" -> "20000105T0600Z/run_model"
   "20000101T0000Z/prep" -> "20000305T1200Z/run_model"
   "20000101T0000Z/prep" -> "20000528T1336Z/run_model"
   "20000105T0600Z/run_model" -> "20000105T0600Z/plot"
   "20000105T0600Z/run_model" -> "20000305T1200Z/run_model"
   "20000305T1200Z/run_model" -> "20000305T1200Z/plot"
   "20000305T1200Z/run_model" -> "20000528T1336Z/run_model"
   "20000528T1336Z/run_model" -> "20000528T1336Z/plot"
   "20000528T1336Z/run_model" -> "20010105T2324Z/run_model"
   "20010101T0000Z/prep" -> "20010105T2324Z/run_model"
   "20010105T2324Z/run_model" -> "20010105T2324Z/plot"
