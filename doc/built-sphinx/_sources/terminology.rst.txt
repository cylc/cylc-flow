Cylc Terminology
================


Jobs and Tasks
--------------

A *job* is a program or script that runs on a computer, and a *task* is
a workflow abstraction - a node in the suite dependency graph - that represents
a job.


Cycle Points
------------

A *cycle point* is a particular date-time (or integer) point in a sequence
of date-time (or integer) points. Each cylc task has a private cycle point and
can advance independently to subsequent cycle points. It may sometimes be
convenient, however, to refer to the "current cycle point" of a suite (or the
previous or next one, etc.) with reference to a particular task, or in the
sense of all tasks instances that "belong to" a particular cycle point. But
keep in mind that different tasks may pass through the "current cycle point"
(etc.) at different times as the suite evolves.


.. only:: builder_html

   .. include:: custom/whitespace_include
