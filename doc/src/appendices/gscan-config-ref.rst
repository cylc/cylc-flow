.. _GscanRCReference:

Gscan GUI (cylc gscan) Config File Reference
============================================

This section defines all legal items and values for the gscan config
file which should be located in ``$HOME/.cylc/gscan.rc``. Some items
also affect the gpanel panel app.

The main menubar can be hidden to maximise the display area. Its visibility
can be toggled via the mouse right-click menu, or by typing ``Alt-m``. When
visible, the main View menu allows you to change properties such as the columns
that are displayed, which hosts to scan for running suites, and the task state
icon theme.

At startup, the task state icon theme and icon size are taken from the gcylc
config file ``$HOME/.cylc/gcylc.rc``.


Top Level Items
---------------


activate on startup
^^^^^^^^^^^^^^^^^^^

Set whether ``cylc gpanel`` will activate automatically when the GUI is
loaded or not.

- *type*: boolean (True or False)
- *legal values*: ``True``, ``False``
- *default*: ``False``
- *example*: ``activate on startup = True``


columns
^^^^^^^

Set the columns to display when the ``cylc gscan`` GUI starts. This can
be changed later with the View menu.  The order in which the columns are
specified here does not affect the display order.

- *type*: string (a list of one or more view names)
- *legal values*: ``host``, ``owner``, ``status``, ``suite``,
  ``title``, ``updated``
- *default*: ``status``, ``suite``
- *example*: ``columns = suite, title, status``


suite listing update interval
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Set the time interval between refreshing the suite listing (by file system or
port range scan).

Increasing this setting will reduce the frequency of gscan looking for running
suites. Scanning for suites by port range scan can be a hit on the network and
the running suite processes, while scanning for suites by walking the file
system can hit the file system (especially if the file system is a network file
system). Therefore, this is normally set with a lower frequency than the status
update interval. Increasing this setting will make gscan friendlier to the
network and/or the file system, but gscan may appear out of sync if there are
many start up or shut down of suites between the intervals.

- *type*: ISO 8601 duration/interval representation (e.g. ``PT10S``,
  10 seconds, or ``PT1M``, 1 minute).
- *default*: PT1M


suite status update interval
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Set the time interval between calls to known running suites (suites that are
known via the latest suite listing) for data updates.

Increasing this setting will reduce the network traffic and hits on the suite
processes. However, gscan may appear out of sync with what may be happening
in very busy suites.

- *type*: ISO 8601 duration/interval representation (e.g. ``PT10S``,
  10 seconds, or ``PT1M``, 1 minute).
- *default*: PT15S


window size
^^^^^^^^^^^

Sets the size in pixels of the ``cylc gscan`` GUI window at startup.

- *type*: integer list: x, y
- *legal values*: positive integers
- *default*: 300, 200
- *example*: ``window size = 1000, 700``


hide main menubar
^^^^^^^^^^^^^^^^^

Hide the main menubar of the ``cylc gscan`` GUI window at startup. By
default, the menubar is not hidden. Either way, you can toggle its
visibility with ``Alt-m`` or via the right-click menu.

- *type*: boolean (True or False)
- *default*: False
- *example*: ``hide main menubar = True``
