Style Guidelines
================

Coding style is largely subjective, but for collaborative development of
complex systems it is important to settle on a clear and consistent style to
avoid getting into a mess. The following style rules are recommended.


Tab Characters
--------------

Do not use tab characters. Tab width depends on editor settings, so a mixture
of tabs and spaces in the same file can render to a mess.

Use ``grep -InPr "\t" *`` to find tabs recursively in files in
a directory.

In *vim* use ``%retab`` to convert existing tabs to spaces,
and set ``expandtab`` to automatically convert new tabs.

In *emacs* use *whitespace-cleanup*.

In *gedit*, use the *Draw Spaces* plugin to display tabs and spaces.


Trailing Whitespace
-------------------

Trailing whitespace is untidy, it makes quick reformatting of paragraphs
difficult, and it can result in hard-to-find bugs (space after intended
line continuation markers).

To remove existing trailing whitespace in a file use a ``sed`` or
``perl`` one-liner:

.. code-block:: bash

   $ perl -pi -e "s/ +$//g" /path/to/file
   # or:
   $ sed --in-place 's/[[:space:]]\+$//' path/to/file

Or do a similar search-and-replace operation in your editor. Editors like
*vim* and *emacs* can also be configured to highlight or automatically
remove trailing whitespace on the fly.


Indentation
-----------

Consistent indentation makes a suite definition more readable, it shows section
nesting clearly, and it makes block re-indentation operations easier in text
editors. Indent suite.rc syntax four spaces per nesting level:


Config Items
^^^^^^^^^^^^

.. code-block:: cylc

   [SECTION]
       # A comment.
       title = the quick brown fox
       [[SUBSECTION]]
           # Another comment.
           a short item = value1
           a very very long item = value2

Don't align ``item = value`` pairs on the ``=`` character
like this:

.. code-block:: cylc

   [SECTION]  # Avoid this.
                a short item = value1
       a very very long item = value2

or like this:

.. code-block:: cylc

   [SECTION]  # Avoid this.
       a short item          = value1
       a very very long item = value2

because the whole block may need re-indenting after a single change, which will
pollute your revision history with spurious changes.

Comments should be indented to the same level as the section or item they refer
to, and trailing comments should be preceded by two spaces, as shown above.


Script String Lines
^^^^^^^^^^^^^^^^^^^

Script strings are written verbatim to task job scripts so they should really
be indented from the left margin:

.. code-block:: cylc

   [runtime]
       [[foo]]
           # Recommended.
           post-script = """
   if [[ $RESULT == "bad" ]]; then
       echo Goodbye World!
       exit 1
   fi"""

Indentation is *mostly* ignored by the bash interpreter, but is useful for
readability. It is *mostly* harmless to indent internal script lines as if
part of the Cylc syntax, or even out to the triple quotes:

.. code-block:: cylc

   [runtime]
       [[foo]]
           # OK, but...
           post-script = """
               if [[ $RESULT == "bad" ]]; then
                   echo Goodbye World!
                   exit 1
               fi"""

On parsing the triple quoted value, Cylc will remove any common leading
whitespace from each line using the logic of
`Python's textwrap.dedent <https://docs.python.org/2/library/textwrap.html#textwrap.dedent>`_
so the script block would end up being the same as the previous example.
However, you should watch your line length (see :ref:`Line Length`) when you
have many levels of indentations.

.. note::

   Take care when indenting here documents:

   .. code-block:: cylc

      [runtime]
          [[foo]]
           script = """
           cat >> log.txt <<_EOF_
               The quick brown fox jumped
               over the lazy dog.
           _EOF_
                    """

In the above, each line in ``log.txt`` would end up with 4 leading
white spaces. The following will give you lines with no white spaces.

.. code-block:: cylc

   [runtime]
       [[foo]]
           script = """
           cat >> log.txt <<_EOF_
           The quick brown fox jumped
           over the lazy dog.
           _EOF_
                    """


Graph String Lines
^^^^^^^^^^^^^^^^^^

Multiline ``graph`` strings can be entirely free-form:

.. code-block:: cylc

   [scheduling]
       [[dependencies]]
           graph = """
       # Main workflow:
     FAMILY:succeed-all => bar & baz => qux

       # Housekeeping:
     qux => rose_arch => rose_prune"""

Whitespace is ignored in graph string parsing, however, so internal graph lines
can be indented as if part of the suite.rc syntax, or even out to the triple
quotes, if you feel it aids readability (but watch line length with large
indents; see :ref:`Line Length`):

.. code-block:: cylc

   [scheduling]
       [[dependencies]]
           graph = """
               # Main workflow:
               FAMILY:succeed-all => bar & baz => qux

               # Housekeeping:
               qux => rose_arch => rose_prune"""

Both styles are acceptable; choose one and use it consistently.


Jinja2 Code
^^^^^^^^^^^

A suite.rc file with embedded Jinja2 code is essentially a Jinja2 program to
generate a Cylc suite definition. It is not possible to consistently indent the
Jinja2 as if it were part of the suite.rc syntax (which to the Jinja2 processor
is just arbitrary text), so it should be indented from the left margin on
its own terms:

.. code-block:: cylc

   [runtime]
       [[OPS]]
   {% for T in OPS_TASKS %}
       {% for M in range(M_MAX) %}
       [[ops_{{T}}_{{M}}]]
           inherit = OPS
       {% endfor %}
   {% endfor %}


Comments
--------

Comments should be minimal, but not too minimal. If context and clear
task and variable names will do, leave it at that. Extremely verbose comments
tend to get out of sync with the code they describe, which can be worse
than having no comments.

Avoid long lists of numbered comments - future changes may require mass
renumbering.

Avoid page-width "section divider" comments, especially if they are not
strictly limited to the standard line length (see :ref:`Line Length`).

Indent comments to the same level as the config items they describe.


Titles, Descriptions, And URLs
------------------------------

Document the suite and its tasks with ``title``,
``description``, and ``url`` items instead of comments. These
can be displayed, or linked to, by the GUI at runtime.


.. _Line Length:

Line Length And Continuation
----------------------------

Keep to the standard maximum line length of 79 characters where possible. Very
long lines affect readability and make side-by-side diffs hard to view.

Backslash line continuation markers can be used anywhere in the suite.rc file
but should be avoided if possible because they are easily broken by invisible
trailing whitespace.

Continuation markers are not needed in graph strings where trailing
trigger arrows imply line continuation:

.. code-block:: cylc

   [scheduling]
       [[dependencies]]
           # No line continuation marker is needed here.
           graph = """prep => one => two => three =>
                   four => five six => seven => eight"""
   [runtime]
       [[MY_TASKS]]
       # A line continuation marker *is* needed here:
       [[one, two, three, four, five, six, seven, eight, nine, ten, \
         eleven, twelve, thirteen ]]
           inherit = MY_TASKS


Task Naming Conventions
-----------------------

Use ``UPPERCASE`` for family names and ``lowercase``
for tasks, so you can distinguish them at a glance.

Choose a convention for multi-component names and use it consistently. Put the
most general name components first for natural grouping in the GUI, e.g.
``obs_sonde``, ``obs_radar`` (not ``sonde_obs`` etc.)

Within your convention keep names as short as possible.


UM System Task Names
^^^^^^^^^^^^^^^^^^^^

For UM System suites we recommend the following full task naming convention:

.. code-block:: none

   model_system_function[_member]

For example, ``glu_ops_process_scatwind`` where ``glu`` refers
to the global (deterministic model) update run, ``ops`` is the system
that owns the task, and ``process_scatwind`` is the function it
performs. The optional ``member`` suffix is intended for use with
ensembles as needed.

Within this convention keep names as short as possible, e.g. use
``fcst`` instead of ``forecast``.

UM forecast apps should be given names that reflect their general science
configuration rather than geographic domain, to allow use on other model
domains without causing confusion.


Rose Config Files
-----------------

Use ``rose config-dump`` to load and re-save new Rose .conf files. This
puts the files in a standard format (ordering of lines etc.) to ensure that
spurious changes aren't generated when you next use ``rose edit``.

See also :ref:`Optional App Config Files` on optional app config files.
