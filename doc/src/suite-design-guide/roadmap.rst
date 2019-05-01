Roadmap
=======

Several planned future developments in Rose and Cylc may have an impact on
suite design.


.. _List Item Override In Site Include-Files:

List Item Override In Site Include-Files
----------------------------------------


A few Cylc config items hold lists of task (or family) names, e.g.:

.. code-block:: cylc

   [scheduling]
       [[special tasks]]
           clock-trigger = get-data-a, get-data-b
       #...
   #...

Currently a repeated config item completely overrides a previously set value
(apart from graph strings which are always additive). This means a site
include-file (for example) can't add a new site-specific clock-triggered task
without writing out the complete list of all clock-triggered tasks in the
suite, which breaks the otherwise clean separation into core and site files.

.. note::

   In the future we `plan to <https://github.com/cylc/cylc-flow/issues/1363>`_
   support add, subtract, unset, and override semantics for all items.


.. _UM STASH in Optional App Configs:

UM STASH in Optional App Configs
--------------------------------


A caveat to the advice on use of option app configs in
:ref:`Optional App Config Files`: in general you might need the ability
to turn off or modify some STASH requests in the main
app, not just add additional site-specific
STASH. But overriding STASH in optional configs is fragile because STASH
namelists names are automatically generated from a *hash* of the precise
content of the namelist. This makes it possible to uniquely identify the same
STASH requests in different apps, but if any detail of a STASH request changes
in a main app its namelist name will change and any optional configs that refer
to it will become divorced from their intended target.

Until this problem is solved we recommend that:

- All STASH in main UM apps should be grouped into sensible
  *packages* that can be turned on and off in optional configs without
  referencing the individual STASH request namelists.
- Or all STASH should be held in optional site configs and none in the
  main app. Note however that STASH is difficult to configure outside of
  ``rose edit``, and the editor `does not yet allow you to edit optional
  configs <https://github.com/metomi/rose/issues/1685>`_.


Modular Suite Design
--------------------

The `modular suite design concept <https://github.com/cylc/cylc/issues/1829>`_
is that we should be able to import common workflow segments at install time
rather than duplicating them in each suite. The content of a suite module
will be encapsulated in a protected namespace to avoid clashing with the
importing suite, and selected inputs and outputs exposed via a proper interface.

This should aid portable suite design too by enabling site-specific parts of a
workflow (local product generation for example) to be stored and imported
on-site rather than polluting the source and revision control record of
the core suite that everyone sees.

We note that this can already be done to a limited extent by using 
``rose suite-run`` to install suite.rc fragments from an external
location. However, as a literal inlining mechanism with no encapsulation or 
interface, the internals of the "imported" fragments would have to be
compatible with the suite definition in every respect.

See also :ref:`Monolithic Or Interdependent Suites` on modular *systems of
suites* connected by inter-suite triggering.
