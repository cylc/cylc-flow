.. _GcylcRCReference:

Gcylc GUI (cylc gui) Config File Reference
==========================================

This section defines all legal items and values for the gcylc user config file,
which should be located in ``$HOME/.cylc/gcylc.rc``. Current settings
can be printed with the ``cylc get-gui-config`` command.


Top Level Items
---------------

dot icon size
^^^^^^^^^^^^^

Set the size of the task state dot icons displayed in the text and dot
views.

- *type*: string
- *legal values*: ``small`` (10px), ``medium`` (14px), ``large`` (20px),
  ``extra large`` (30px)
- *default*: ``medium``


initial side-by-side views
^^^^^^^^^^^^^^^^^^^^^^^^^^

Set the suite view panels initial orientation when the GUI starts.
This can be changed later using the "View" menu "Toggle views side-by-side"
option.

- *type*: boolean (False or True)
- *default*: ``False``


initial views
^^^^^^^^^^^^^

Set the suite view panel(s) displayed initially, when the GUI starts.
This can be changed later using the tool bar.

- *type*: string (a list of one or two view names)
- *legal values*: ``text``, ``dot``,  ``graph``
- *default*: ``text``
- *example*: ``initial views = graph, dot``


maximum update interval
^^^^^^^^^^^^^^^^^^^^^^^

Set the maximum (longest) time interval between calls to the suite for data
update.

The update frequency of the GUI is variable. It is determined by considering
the time of last update and the mean duration of the last 10 main loops of the
suite.

In general, the GUI will use an update frequency that matches the mean duration
of the suite's main loop. In quiet time (or if the suite is not contactable),
it will gradually increase the update interval (i.e. reduce the update
frequency) to a maximum determined by this setting.

Increasing this setting will reduce the network traffic and hits on the suite
process.  However, if a quiet suite starts to pick up activity, the GUI may
initially appear out of sync with what is happening in the suite for the
duration of this interval.

- *type*: ISO 8601 duration/interval representation (e.g.
  ``PT10S``, 10 seconds, or ``PT1M``, 1 minute).
- *default*: PT15S


sort by definition order
^^^^^^^^^^^^^^^^^^^^^^^^

If this is not turned off the default sort order for task names and
families in the dot and text views will the order they appear in the
suite definition. Clicking on the task name column in the treeview will
toggle to alphanumeric sort, and a View menu item does the same for the
dot view.  If turned off, the default sort order is alphanumeric and
definition order is not available at all.

- *type*: boolean
- *default*: ``True``


sort column
^^^^^^^^^^^

If ``text`` is in ``initial views`` then ``sort column`` sets
the column that will be sorted initially when the GUI launches. Sorting can be
changed later by clicking on the column headers.

- *type*: string
- *legal values*: ``task``, ``state``, ``host``, ``job system``,
  ``job ID``, ``T-submit``, ``T-start``, ``T-finish``, ``dT-mean``,
  ``latest message``, ``none``
- *default*: ``none``
- *example*: ``sort column = T-start``


sort column ascending
^^^^^^^^^^^^^^^^^^^^^

For use in combination with ``sort column``, sets whether the column will
be sorted using ascending or descending order.

- *type*: boolean
- *default*: ``True``
- *example*: ``sort column ascending = False``


sub-graphs on
^^^^^^^^^^^^^

Set the sub-graphs view to be enabled by default.
This can be changed later using the toggle options for the graph view.

- *type*: boolean (False or True)
- *default*: ``False``


task filter highlight color
^^^^^^^^^^^^^^^^^^^^^^^^^^^

The color used to highlight active task filters in gcylc. It must be a name
from the X11 ``rgb.txt`` file, e.g. ``SteelBlue``; or a
*quoted* hexadecimal color code, e.g. ``"#ff0000"`` for red (quotes
are required to prevent the hex code being interpreted as a comment).

- *type*: string
- *default*: ``PowderBlue``


task states to filter out
^^^^^^^^^^^^^^^^^^^^^^^^^

Set the initial filtering options when the GUI starts. Later this can be
changed by using the "View" menu "Task Filtering" option.

- *type*: string list
- *legal values*: waiting, held, queued, ready, expired, submitted,
  submit-failed, submit-retrying, running, succeeded, failed, retrying,
  runahead
- *default*: runahead


transpose dot
^^^^^^^^^^^^^

Transposes the content in dot view so that it displays from left to right
rather than from top to bottom. Can be changed later using the options
submenu available via the view menu.

- *type*: boolean
- *default*: ``False``
- *example*: ``transpose dot = True``


transpose graph
^^^^^^^^^^^^^^^

Transposes the content in graph view so that it displays from left to right
rather than from top to bottom. Can be changed later using the options submenu
via the view menu.

- *type*: boolean
- *default*: ``False``
- *example*: ``transpose graph = True``


ungrouped views
^^^^^^^^^^^^^^^

List suite views, if any, that should be displayed initially in an
ungrouped state. Namespace family grouping can be changed later
using the tool bar.

- *type*: string (a list of zero or more view names)
- *legal values*: ``text``, ``dot``,  ``graph``
- *default*: (none)
- *example*: ``ungrouped views = text, dot``


use theme
^^^^^^^^^

Set the task state color theme, common to all views, to use initially. The
color theme can be changed later using the tool bar.  See
``etc/gcylc.rc.eg`` and ``etc/gcylc-themes.rc`` in the Cylc
installation directory for how to modify existing themes or define your own.
Use ``cylc get-gui-config`` to list available themes.

- *type*: string (theme name)
- *legal values*: ``default``, ``solid``, ``high-contrast``,
  ``color-blind``, and any custom or user-modified themes.
- *default*: ``default``


window size
^^^^^^^^^^^

Sets the size (in pixels) of the cylc GUI at startup.

- *type*: integer list: x, y
- *legal values*: positive integers
- *default*: 800, 500
- *example*: ``window size = 1000, 700``


[themes]
--------

This section may contain task state color theme definitions.


[themes] ``->`` [[THEME]]
^^^^^^^^^^^^^^^^^^^^^^^^^

The name of the task state color-theme to be defined in this section.

- *type*: string


[themes] ``->`` [[THEME]] ``->`` inherit
""""""""""""""""""""""""""""""""""""""""

You can inherit from another theme in order to avoid defining all states.

- *type*: string (parent theme name)
- *default*: ``default``


[themes] ``->`` [[THEME]] ``->`` defaults
"""""""""""""""""""""""""""""""""""""""""

Set default icon attributes for all state icons in this theme.

- *type*: string list (icon attributes)
- *legal values*: ``"color=COLOR"``, ``"style=STYLE"``,
  ``"fontcolor=FONTCOLOR"``
- *default*: (none)

For the attribute values, ``COLOR`` and ``FONTCOLOR`` can be color names from
the X11 ``rgb.txt`` file, e.g. ``SteelBlue``; or hexadecimal color codes, e.g.
``#ff0000`` for red; and ``STYLE`` can be ``filled`` or ``unfilled``.
See ``etc/gcylc.rc.eg`` and ``etc/gcylc-themes.rc`` in
the Cylc installation directory for examples.


[themes] ``->`` [[THEME]] ``->`` STATE
""""""""""""""""""""""""""""""""""""""

Set icon attributes for all task states in ``THEME``, or for a subset of them
if you have used theme inheritance and/or defaults. Legal values of ``STATE``
are any of the cylc task proxy states: *waiting, runahead, held, queued,
ready, submitted, submit-failed, running, succeeded, failed, retrying,
submit-retrying*.

- *type*: string list (icon attributes)
- *legal values*: ``"color=COLOR"``, ``"style=STYLE"``,
  ``"fontcolor=FONTCOLOR"``
- *default:* (none)

For the attribute values, ``COLOR`` and ``FONTCOLOR`` can be color names from
the X11 ``rgb.txt`` file, e.g. ``SteelBlue``; or hexadecimal color codes, e.g.
``#ff0000`` for red; and ``STYLE`` can be ``filled`` or ``unfilled``.
See ``etc/gcylc.rc.eg`` and ``etc/gcylc-themes.rc`` in
the Cylc installation directory for examples.
