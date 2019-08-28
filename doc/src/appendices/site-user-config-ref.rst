.. _SiteRCReference:

Global (Site, User) Config File Reference
=========================================

This section defines all legal items and values for cylc site and
user config files. See :ref:`SiteAndUserConfiguration` for file locations,
intended usage, and how to generate the files using the
``cylc get-site-config`` command.

*As for suite configurations, Jinja2 expressions can be embedded in
site and user config files to generate the final result parsed by cylc.*
Use of Jinja2 in suite configurations is documented in :ref:`Jinja`.


Top Level Items
---------------


temporary directory
^^^^^^^^^^^^^^^^^^^

A temporary directory is needed by a few cylc commands, and is cleaned
automatically on exit. Leave unset for the default (usually ``$TMPDIR``).

- *type*: string (directory path)
- *default*: (none)
- *example*: ``temporary directory = /tmp/$USER/cylc``


.. _process pool size:

process pool size
^^^^^^^^^^^^^^^^^

Maximum number of concurrent processes used to execute external job
submission, event handlers, and job poll and kill commands - see
:ref:`Managing External Command Execution`.

- *type*: integer
- *default*: 4


.. _process pool timeout:

process pool timeout
^^^^^^^^^^^^^^^^^^^^

Interval after which long-running commands in the process pool will be killed -
see :ref:`Managing External Command Execution`.

- *type*: ISO 8601 duration/interval representation (e.g.
  ``PT10S``, 10 seconds, or ``PT1M``, 1 minute).
- *default*: PT10M -  note this is set quite high to avoid killing
  important processes when the system is under load.


disable interactive command prompts
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Commands that intervene in running suites can be made to ask for
confirmation before acting. Some find this annoying and ineffective as a
safety measure, however, so command prompts are disabled by default.

- *type*: boolean
- *default*: True


task host select command timeout
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When a task host in a suite is a shell command string, cylc calls the shell to
determine the task host. This call is invoked by the main process, and may
cause the suite to hang while waiting for the command to finish. This setting
sets a timeout for such a command to ensure that the suite can continue.

- *type*: ISO 8601 duration/interval representation (e.g.
  ``PT10S``, 10 seconds, or ``PT1M``, 1 minute).
- *default*: PT10S


[task messaging]
----------------

This section contains configuration items that affect task-to-suite
communications.


[retry interval]{[task messaging] ``->`` retry interval
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If a send fails, the messaging code will retry after a configured
delay interval.

- *type*: ISO 8601 duration/interval representation (e.g.
  ``PT10S``, 10 seconds, or ``PT1M``, 1 minute).
- *default*: PT5S


[maximum number of tries]{[task messaging] ``->`` maximum number of tries
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If successive sends fail, the messaging code will give up after a
configured number of tries.

- *type*: integer
- *minimum*: 1
- *default*: 7


[connection timeout]{[task messaging] ``->`` connection timeout
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This is the same as the ``--comms-timeout`` option in cylc
commands. Without a timeout remote connections to unresponsive
suites can hang indefinitely (suites suspended with Ctrl-Z for instance).

- *type*: ISO 8601 duration/interval representation (e.g.
  ``PT10S``, 10 seconds, or ``PT1M``, 1 minute).
- *default*: PT30S


[suite logging]
---------------

The suite event log, held under the suite run directory, is maintained
as a rolling archive. Logs are rolled over (backed up and started anew)
when they reach a configurable limit size.


[rolling archive length]{[suite logging] ``->`` rolling archive length
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

How many rolled logs to retain in the archive.

- *type*: integer
- *minimum*: 1
- *default*: 5


maximum size in bytes]{[suite logging] ``->`` maximum size in bytes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Suite event logs are rolled over when they reach this file size.

- *type*: integer
- *default*: 1000000


[documentation]
---------------

Documentation locations for the ``cylc doc`` command and gcylc
Help menus.


[documentation] ``->`` [[files]]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

File locations of documentation held locally on the cylc host server.


[documentation] ``->`` [[files]] ``->`` html index
""""""""""""""""""""""""""""""""""""""""""""""""""

File location of the main cylc documentation index.

- *type*: string
- *default*: ``<cylc-dir>/doc/index.html``


[documentation] ``->`` [[files]] ``->`` pdf user guide
""""""""""""""""""""""""""""""""""""""""""""""""""""""

File location of the cylc User Guide, PDF version.

- *type*: string
- *default*: ``<cylc-dir>/doc/cug-pdf.pdf``


[documentation] ``->`` [[files]] ``->`` multi-page html user guide
""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

File location of the cylc User Guide, multi-page HTML version.

- *type*: string
- *default*: ``<cylc-dir>/doc/html/multi/cug-html.html``


[documentation] ``->`` [[files]] ``->`` single-page html user guide
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

File location of the cylc User Guide, single-page HTML version.

- *type*: string
- *default*: ``<cylc-dir>/doc/html/single/cug-html.html``


[documentation] ``->`` [[urls]]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Online documentation URLs.


[documentation] ``->`` [[urls]] ``->`` internet homepage
""""""""""""""""""""""""""""""""""""""""""""""""""""""""

URL of the cylc internet homepage, with links to documentation for the
latest official release.

- *type*: string
- *default*: http://cylc.github.com/cylc/


[documentation] ``->`` [[urls]] ``->`` local index
""""""""""""""""""""""""""""""""""""""""""""""""""

Local intranet URL of the main cylc documentation index.

- *type*: string
- *default*: (none)


[document viewers]
------------------

PDF and HTML viewers can be launched by cylc to view the documentation.


[document viewers] ``->`` pdf
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Your preferred PDF viewer program.

- *type*: string
- *default*: evince


[document viewers] ``->`` html
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Your preferred web browser.

- *type*: string
- *default*: firefox


[editors]
---------

Choose your favourite text editor for editing suite configurations.


[editors] ``->`` terminal
^^^^^^^^^^^^^^^^^^^^^^^^^

The editor to be invoked by the cylc command line interface.

- *type*: string
- *default*: ``vim``
- *examples*:
  - ``terminal = emacs -nw`` (emacs non-GUI)
  - ``terminal = emacs`` (emacs GUI)
  - ``terminal = gvim -f`` (vim GUI)


[editors] ``->`` gui
^^^^^^^^^^^^^^^^^^^^

The editor to be invoked by the cylc GUI.

- *type*: string
- *default*: ``gvim -f``
- *examples*:
  - ``gui = emacs``
  - ``gui = xterm -e vim``


[communication]
---------------

This section covers options for network communication between cylc
clients (suite-connecting commands and guis) servers (running suites).
Each suite listens on a dedicated network port, binding on the first
available starting at the configured base port.

By default, the communication method is HTTPS secured with HTTP Digest
Authentication. If the system does not support SSL, you should configure
this section to use HTTP. Cylc will not automatically fall back to HTTP
if HTTPS is not available.


[communication] ``->`` method
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The choice of client-server communication method - currently only HTTPS
and HTTP are supported, although others could be developed and plugged in.
Cylc defaults to HTTPS if this setting is not explicitly configured.

- *type*: string
- *options*:
  - **https**
  - **http**
- *default*: https


[communication] ``->`` base port
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The first port that Cylc is allowed to use. This item (and
``maximum number of ports``) is deprecated; please use
``run ports`` under ``[suite servers]`` instead.

- *type*: integer
- *default*: ``43001``


[communication] ``->`` maximum number of ports
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This setting (and ``base port``) is deprecated; please use
``run ports`` under ``[suite servers]`` instead.

- *type*: integer
- *default*: ``100``


[communication] ``->`` proxies on
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Enable or disable proxy servers for HTTPS - disabled by default.

- *type*: boolean
- *localhost default*: False


[communication] ``->`` options
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Option flags for the communication method. Currently only 'SHA1' is
supported for HTTPS, which alters HTTP Digest Auth to use the SHA1 hash
algorithm rather than the standard MD5. This is more secure but is also
less well supported by third party web clients including web browsers.
You may need to add the 'SHA1' option if you are running on platforms
where MD5 is discouraged (e.g. under FIPS).

- *type*: string\_list
- *default*: ``[]``
- *options*:
  - **SHA1**


[monitor]
---------

Configurable settings for the command line ``cylc monitor`` tool.


[monitor] ``->`` sort order
^^^^^^^^^^^^^^^^^^^^^^^^^^^

The sort order for tasks in the monitor view.

- *type*: string
- *options*:

  - **alphanumeric**
  - **definition** -  the order that tasks appear under
    ``[runtime]`` in the suite configuration.

- *default*: definition


[hosts]
-------

The [hosts] section configures some important host-specific settings for
the suite host ("localhost") and remote task hosts.

.. note::

   Remote task behaviour is determined by the site/user config on the
   suite host, not on the task host.

Suites can specify task hosts that
are not listed here, in which case local settings will be assumed,
with the local home directory path, if present, replaced by
``$HOME`` in items that configure directory locations.


[hosts] ``->`` [[HOST]]
^^^^^^^^^^^^^^^^^^^^^^^

The default task host is the suite host, **localhost**, with default
values as listed below. Use an explicit ``[hosts][[localhost]]``
section if you need to override the defaults. Localhost settings are
then also used as defaults for other hosts, with the local home
directory path replaced as described above. This applies to items
omitted from an explicit host section, and to hosts that are not listed
at all in the site and user config files.  Explicit host sections are only
needed if the automatically modified local defaults are not sufficient.

Host section headings can also be *regular expressions* to match
multiple hostnames.

.. note::

   The general regular expression wildcard
   is ``'.*'`` (zero or more of any character), not ``'*'``.
   Hostname matching regular expressions are used as-is in the Python
   ``re.match()`` function.

As such they match from the beginning
of the hostname string (as specified in the suite configuration) and they
do not have to match through to the end of the string (use the
string-end matching character ``'$'`` in the expression to force this).

A hierarchy of host match expressions from specific to general can be
used because config items are processed in the order specified in the
file.

- *type*: string (hostname or regular expression)
- *examples*:
  - ``server1.niwa.co.nz`` - explicit host name
  - ``server\d.niwa.co.nz`` - regular expression


[hosts] ``->`` [[HOST]] ``->`` run directory
""""""""""""""""""""""""""""""""""""""""""""

The top level for suite logs and service files, etc. Can contain
``$HOME`` or ``$USER`` but not other environment variables (the
item cannot actually be evaluated by the shell on HOST before use, but the
remote home directory is where ``rsync`` and ``ssh`` naturally
land, and the remote username is known by the suite server program).

- *type*: string (directory path)
- *default*: ``$HOME/cylc-run``
- *example*: ``/nfs/data/$USER/cylc-run``


.. _workdirectory:

[hosts] ``->`` [[HOST]] ``->`` work directory
"""""""""""""""""""""""""""""""""""""""""""""

The top level for suite work and share directories. Can contain
``$HOME`` or ``$USER`` but not other environment variables
(the item cannot actually be evaluated by the shell on HOST before use, but the
remote home directory is where ``rsync`` and ``ssh`` naturally
land, and the remote username is known by the suite server program).

- *type*: string (directory path)
- *localhost default*: ``$HOME/cylc-run``
- *example*: ``/nfs/data/$USER/cylc-run``


.. _task_comms_method:

[hosts] ``->`` [[HOST]] ``->`` task communication method
""""""""""""""""""""""""""""""""""""""""""""""""""""""""

The means by which task progress messages are reported back to the running suite.
See above for default polling intervals for the poll method.

- *type*: string (must be one of the following three options)
- *options*:
  - **default** - direct client-server communication via network ports
  - **ssh** - use ssh to re-invoke the messaging commands on the suite server
  - **poll** - the suite polls for the status of tasks (no task messaging)
- *localhost default*: default


.. _execution_polling:

[hosts] ``->`` [[HOST]] ``->`` execution polling intervals
""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

Cylc can poll running jobs to catch problems that prevent task messages
from being sent back to the suite, such as hard job kills, network
outages, or unplanned task host shutdown. Routine polling is done only
for the polling *task communication method* (below) unless
suite-specific polling is configured in the suite configuration.
A list of interval values can be specified, with the last value used
repeatedly until the task is finished - this allows more frequent
polling near the beginning and end of the anticipated task run time.
Multipliers can be used as shorthand as in the example below.

- *type*: ISO 8601 duration/interval representation (e.g.
  ``PT10S``, 10 seconds, or ``PT1M``, 1 minute).
- *default*:
- *example*: ``execution polling intervals = 5*PT1M, 10*PT5M, 5*PT1M``


.. _submission_polling:

[hosts] ``->`` [[HOST]] ``->`` submission polling intervals
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

Cylc can also poll submitted jobs to catch problems that prevent the
submitted job from executing at all, such as deletion from an external
batch scheduler queue. Routine polling is done only for the polling
*task communication method* (above) unless suite-specific polling
is configured in the suite configuration. A list of interval
values can be specified as for execution polling (above) but a single
value is probably sufficient for job submission polling.

- *type*: ISO 8601 duration/interval representation (e.g.
  ``PT10S``, 10 seconds, or ``PT1M``, 1 minute).
- *default*:
- *example*: (see the execution polling example above)


[hosts] ``->`` [[HOST]] ``->`` scp command
""""""""""""""""""""""""""""""""""""""""""

A string for the command used to copy files to a remote host. This is not used
on the suite host unless you run local tasks under another user account. The
value is assumed to be ``scp`` with some initial options or a command
that implements a similar interface to ``scp``.

- *type*: string
- *localhost default*: ``scp -oBatchMode=yes -oConnectTimeout=10``


[hosts] ``->`` [[HOST]] ``->`` ssh command
""""""""""""""""""""""""""""""""""""""""""

A string for the command used to invoke commands on this host. This is not
used on the suite host unless you run local tasks under another user account.
The value is assumed to be ``ssh`` with some initial options or a
command that implements a similar interface to ``ssh``.

- *type*: string
- *localhost default*: ``ssh -oBatchMode=yes -oConnectTimeout=10``


[hosts] ``->`` [[HOST]] ``->`` use login shell
""""""""""""""""""""""""""""""""""""""""""""""

Whether to use a login shell or not for remote command invocation. By
default cylc runs remote ssh commands using a login shell:

.. code-block:: bash

   ssh user@host 'bash --login cylc ...'

which will source ``/etc/profile`` and
``~/.profile`` to set up the user environment.  However, for
security reasons some institutions do not allow unattended commands to
start login shells, so you can turn off this behaviour to get:

.. code-block:: bash

   ssh user@host 'cylc ...'

which will use the default shell on the remote machine,
sourcing ``~/.bashrc`` (or ``~/.cshrc``) to set up the
environment.

- *type*: boolean
- *localhost default*: True


[hosts] ``->`` [[HOST]] ``->`` cylc executable
""""""""""""""""""""""""""""""""""""""""""""""

The ``cylc`` executable on a remote host.

.. note::

   This should normally point to the cylc multi-version wrapper
   (see :ref:`CUI`) on the host, not ``bin/cylc`` for a specific
   installed version.

Specify a full path if ``cylc`` is not in ``\$PATH`` when it is
invoked via ``ssh`` on this host.

- *type*: string
- *localhost default*: ``cylc``


.. _GlobalInitScript:

[hosts] ``->`` [[HOST]] ``->`` global init-script
"""""""""""""""""""""""""""""""""""""""""""""""""

If specified, the value of this setting will be inserted to just before the
``init-script`` section of all job scripts that are to be
submitted to the specified remote host.

- *type*: string
- *localhost default*: ``""``


[hosts] ``->`` [[HOST]] ``->`` copyable environment variables
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

A list containing the names of the environment variables that can and/or need
to be copied from the suite server program to a job.

- *type*: string\_list
- *localhost default*: ``[]``


[hosts] ``->`` [[HOST]] ``->`` retrieve job logs
""""""""""""""""""""""""""""""""""""""""""""""""

Global default for the :ref:`runtime-remote-retrieve-job-logs` setting for
the specified host.


[hosts] ``->`` [[HOST]] ``->`` retrieve job logs command
""""""""""""""""""""""""""""""""""""""""""""""""""""""""

If ``rsync -a`` is unavailable or insufficient to retrieve job logs
from a remote host, you can use this setting to specify a suitable command.

- *type*: string
- *default*: rsync -a


[hosts] ``->`` [[HOST]] ``->`` retrieve job logs max size
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""

Global default for the :ref:`runtime-remote-retrieve-job-logs-max-size`
setting for the specified host.


[hosts] ``->`` [[HOST]] ``->`` retrieve job logs retry delays
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

Global default for the :ref:`runtime-remote-retrieve-job-logs-retry-delays`
setting for the specified host.


[hosts] ``->`` [[HOST]] ``->`` task event handler retry delays
""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

Host specific default for the :ref:`runtime-events-handler-retry-delays`
setting.


.. _tail-command-template:

[hosts] ``->`` [[HOST]] ``->`` tail command template
""""""""""""""""""""""""""""""""""""""""""""""""""""

A command template (with ``%(filename)s`` substitution) to tail-follow
job logs on HOST, by the GUI log viewer and ``cylc cat-log``. You are
unlikely to need to override this.

- *type*: string
- *default*: ``tail -n +1 -F %(filename)s``


[hosts] ``->`` [[HOST]] ``->`` [[[batch systems]]]
""""""""""""""""""""""""""""""""""""""""""""""""""

Settings for particular batch systems on HOST. In the subsections below, SYSTEM
should be replaced with the cylc batch system handler name that represents the
batch system (see :ref:`RuntimeJobSubMethods`).


.. _err-tailer:

[hosts] ``->`` [[HOST]] ``->`` [[[batch systems]]] ``->`` [[[[SYSTEM]]]] ``->`` err tailer
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

A command template (with ``%(job_id)s`` substitution) that can be used
to tail-follow the stderr stream of a running job if SYSTEM does
not use the normal log file location while the job is running.  This setting
overrides :ref:`tail-command-template` above.

- *type*: string
- *default*: (none)
- *example*: For PBS:

.. code-block:: cylc

   [hosts]
       [[ myhpc*]]
           [[[batch systems]]]
               [[[[pbs]]]]
                   err tailer = qcat -f -e %(job_id)s
                   out tailer = qcat -f -o %(job_id)s
                   err viewer = qcat -e %(job_id)s
                   out viewer = qcat -o %(job_id)s


.. _out-tailer:

[hosts] ``->`` [[HOST]] ``->`` [[[batch systems]]] ``->`` [[[[SYSTEM]]]] ``->`` out tailer
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

A command template (with ``%(job_id)s`` substitution) that can be used
to tail-follow the stdout stream of a running job if SYSTEM does
not use the normal log file location while the job is running.  This setting
overrides :ref:`tail-command-template` above.

- *type*: string
- *default*: (none)
- *example*: see :ref:`err-tailer`


[hosts] ``->`` [[HOST]] ``->`` [[[batch systems]]] ``->`` [[[[SYSTEM]]]] ``->`` err viewer
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

A command template (with ``%(job_id)s`` substitution) that can be used
to view the stderr stream of a running job if SYSTEM does
not use the normal log file location while the job is running.

- *type*: string
- *default*: (none)
- *example*: see :ref:`err-tailer`


[hosts] ``->`` [[HOST]] ``->`` [[[batch systems]]] ``->`` [[[[SYSTEM]]]] ``->`` out viewer
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

A command template (with ``%(job_id)s`` substitution) that can be used
to view the stdout stream of a running job if SYSTEM does
not use the normal log file location while the job is running.

- *type*: string
- *default*: (none)
- *example*: see :ref:`err-tailer`


.. _JobNameLengthMaximum:

[hosts] ``->`` [[HOST]] ``->`` [[[batch systems]]] ``->`` [[[[SYSTEM]]]] ``->`` job name length maximum
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

The maximum length for job name acceptable by a batch system on a given host.
Currently, this setting is only meaningful for PBS jobs. For example, PBS 12
or older will fail a job submit if the job name has more than 15 characters,
which is the default setting. If you have PBS 13 or above, you may want to
modify this setting to a larger value.

- *type*: integer
- *default*: (none)
- *example*:  For PBS:

.. code-block:: cylc

   [hosts]
       [[myhpc*]]
           [[[batch systems]]]
               [[[[pbs]]]]
                   # PBS 13
                   job name length maximum = 236


.. _ExecutionTimeLimitPollingIntervals:

[hosts] ``->`` [[HOST]] ``->`` [[[batch systems]]] ``->`` [[[[SYSTEM]]]] ``->`` execution time limit polling intervals
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

The intervals between polling after a task job (submitted to the relevant batch
system on the relevant host) exceeds its execution time limit. The default
setting is PT1M, PT2M, PT7M. The accumulated times (in minutes) for these
intervals will be roughly 1, 1 + 2 = 3 and 1 + 2 + 7 = 10 after a task job
exceeds its execution time limit.

    - *type*: Comma-separated list of ISO 8601 duration/interval
      representations, optionally *preceded* by multipliers.
    - *default*: PT1M, PT2M, PT7M
    - *example*:

.. code-block:: cylc

   [hosts]
       [[myhpc*]]
           [[[batch systems]]]
               [[[[pbs]]]]
                   execution time limit polling intervals = 5*PT2M


.. _global-suite-servers:

[suite servers]
---------------

Configure allowed suite hosts and ports for starting up (running or
restarting) suites and enabling them to be detected whilst running via
utilities such as ``cylc gscan``. Additionally configure host
selection settings specifying how to determine the most suitable run host at
any given time from those configured.


[suite servers] ``->`` auto restart delay
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Relates to Cylc's auto stop-restart mechanism (see :ref:`auto-stop-restart`).
When a host is set to automatically shutdown/restart it will first wait a
random period of time between zero and ``auto restart delay``
seconds before beginning the process. This is to prevent large numbers
of suites from restarting simultaneously. 

- *type*: integer
- *default*: ``0``


[suite servers] ``->`` condemned hosts
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Hosts specified in ``condemned hosts`` will not be considered as suite
run hosts. If suites are already running on ``condemned hosts`` they
will be automatically shutdown and restarted (see :ref:`auto-stop-restart`).

- *type*: comma-separated list of host names and/or IP addresses.
- *default*: (none)


[suite servers] ``->`` run hosts
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A list of allowed suite run hosts. One of these hosts will be appointed for
a suite to start up on if an explicit host is not provided as an option to
a ``run`` or ``restart`` command.

- *type*: comma-separated list of host names and/or IP addresses.
- *default*: ``localhost``


[suite servers] ``->`` scan hosts
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A list of hosts to scan for running suites.

- *type*: comma-separated list of host names and/or IP addresses.
- *default*: ``localhost``


[suite servers] ``->`` run ports
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A list of allowed ports for Cylc to use to run suites.

.. note::

   Only one suite can run per port for a given host, so the length
   of this list determines the maximum number of suites that can run
   at once per suite host.

This config item supersedes the deprecated settings ``base port``
and ``maximum number of ports``, where the base port is equivalent to
the first port, and the maximum number of ports to the length, of this list.

- *type*: string in the format ``X .. Y`` for
  ``X <= Y`` where ``X`` and ``Y`` are integers.
- *default*: ``43001 .. 43100`` (equivalent to the list
  ``43001, 43002, ... , 43099, 43100``)


[suite servers] ``->`` scan ports
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A list of ports to scan for running suites on each host set in scan hosts.

- *type*: string in the format ``X .. Y`` for
  ``X <= Y`` where ``X`` and ``Y`` are integers.
- *default*: ``43001 .. 43100`` (equivalent to the list
  ``43001, 43002, ... , 43099, 43100``)


[suite servers] ``->`` [[run host select]]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Configure thresholds for excluding insufficient hosts and a method for
ranking the remaining hosts to be applied in selection of the most suitable
``run host``, from those configured, at start-up whenever a set host
is not specified on the command line via the ``--host=`` option.


[suite servers] ``->`` [[run host select]] ``->`` rank
""""""""""""""""""""""""""""""""""""""""""""""""""""""

The method to use to rank the ``run host`` list in order of
suitability.

- *type*: string (which must be one of the options outlined below)
- *default*: ``random``
- *options*:

  - **random** - shuffle the hosts to select a host at random
  - **load:1** - rank and select for the lowest load average over
    1 minute (as given by the ``uptime`` command)
  - **load:5** - as for ``load:1`` above, but over 5 minutes
  - **load:15** - as for ``load:1`` above, but over 15 minutes
  - **memory** - rank and select for the highest usable memory i.e.
      free memory plus memory in the buffer cache ('buffers') and in the
      page cache ('cache'), as specified under ``/proc/meminfo``
  - **disk-space:PATH** - rank and select for the highest free disk
      space for a given mount directory path ``PATH`` as given by
      the ``df`` command, where multiple paths may be specified
      individually i.e. via ``disk-space:PATH_1`` and
      ``disk-space:PATH_2``, etc.

- *default*: (none)


[suite servers] ``->`` [[run host select]] ``->`` thresholds
""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

A list of thresholds i.e. cutoff values which run hosts must meet in order
to be considered as a possible run host. Each threshold is a minimum or a
maximum requirement depending on the context of the measure; usable
memory (``memory``) and free disk space
(``disk-space:PATH``) threshold values set a *minimum* value,
which must be exceeded, whereas load average (``load:1``,
``load:5`` and ``load:15``) threshold values set a
*maximum*, which must not be. Failure to meet a threshold results in
exclusion from the list of hosts that undergo ranking to
determine the best host which becomes the run host.

- *type*: string in format ``MEASURE_1 CUTOFF_1; ... ;MEASURE_n CUTOFF_n``
  (etc), where each ``MEASURE_N`` is one of the options below (note
  these correspond to all the rank methods accepted under the rank setting
  except for ``random`` which does not make sense as a threshold
  measure). Spaces delimit corresponding measures and their values, while
  semi-colons (optionally with subsequent spaces) delimit each measure-value
  pair.
- *options*:

  - **load:1** - load average over 1 minute (as given by
    the ``uptime`` command)
  - **load:5** - as for ``load:1`` above, but over 5 minutes
  - **load:15** - as for ``load:1`` above, but over 15 minutes
  - **memory** - usable memory i.e. free memory plus memory in the
    buffer cache ('buffers') and in the page cache ('cache'), in KB, as
    specified under ``/proc/meminfo``
  - **disk-space:PATH** - free disk space for a given mount
    directory path ``PATH``, in KB, as given by the ``df``
    command, where multiple paths may be specified individually i.e. via
    ``disk-space:PATH_1`` and ``disk-space:PATH_2``, etc.

- *default*: (none)
- *examples*:

  - ``thresholds = memory 2000`` (set a minimum of 2000 KB in usable
    memory for possible run hosts)
  - ``thresholds = load:5 0.5; load:15 1.0; disk-space:/ 5000`` (set a maximum
    of 0.5 and 1.0 for load averages over 5
    and 15 minutes respectively and a minimum of 5000 KB of free disk-space on
    the ``/`` mount directory. If any of these thresholds are not met
    by a host, it will be excluded for running a suite on.)


[suite host self-identification]
--------------------------------

The suite host's identity must be determined locally by cylc and passed
to running tasks (via ``$CYLC_SUITE_HOST``) so that task messages
can target the right suite on the right host.

.. todo::

   Is it conceivable that different remote task hosts at the same
   site might see the suite host differently? If so we would need to be
   able to override the target in suite configurations.


[suite host self-identification] ``->`` method
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This item determines how cylc finds the identity of the suite host. For
the default *name* method cylc asks the suite host for its host
name. This should resolve on remote task hosts to the IP address of the
suite host; if it doesn't, adjust network settings or use one of the
other methods. For the *address* method, cylc attempts to use a
special external "target address" to determine the IP address of the
suite host as seen by remote task hosts (in-source documentation in
``<cylc-dir>/lib/cylc/hostuserutil.py`` explains how this works).
And finally, as a last resort, you can choose the *hardwired* method
and manually specify the host name or IP address of the suite host.

- *type*: string
- *options*:

  - name - self-identified host name
  - address - automatically determined IP address (requires *target*,
    below)
  - hardwired - manually specified host name or IP address (requires
    *host*, below)

- *default*: name


[suite host self-identification] ``->`` target
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This item is required for the *address* self-identification method.
If your suite host sees the internet, a common address such as
``google.com`` will do; otherwise choose a host visible on your
intranet.

- *type*: string (an inter- or intranet URL visible from the suite host)
- *default*: ``google.com``


[suite host self-identification] ``->`` host
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Use this item to explicitly set the name or IP address of the suite host
if you have to use the *hardwired* self-identification method.

- *type*: string (host name or IP address)
- *default*: (none)


[task events]
-------------

Global site/user defaults for :ref:`TaskEventHandling`.


[test battery]
--------------

Settings for the automated development tests.

.. note::

   The test battery reads
   ``<cylc-dir>/etc/global-tests.rc`` instead of the normal site/user
   global config files.


[test battery] ``->`` remote host with shared fs
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The name of a remote host that sees the same HOME file system as the host
running the test battery.


[test battery] ``->`` remote host
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Host name of a remote account that does not see the same home directory as
the account running the test battery - see also "remote owner" below).


[test battery] ``->`` remote owner
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

User name of a remote account that does not see the same home directory as the
account running the test battery - see also "remote host" above).


[test battery] ``->`` [[batch systems]]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Settings for testing supported batch systems (job submission methods). The
tests for a batch system are only performed if the batch system is available on
the test host or a remote host accessible via SSH from the test host.


[test battery] ``->`` [[batch systems]] ``->`` [[[SYSTEM]]]
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

SYSTEM is the name of a supported batch system with automated tests.
This can currently be "loadleveler", "lsf", "pbs", "sge" and/or "slurm".


[test battery] ``->`` [[batch systems]] ``->`` [[[SYSTEM]]] ``->`` host
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

The name of a host where commands for this batch system is available. Use
"localhost" if the batch system is available on the host running the test
battery. Any specified remote host should be accessible via SSH from the host
running the test battery.


[test battery] ``->`` [[batch systems]] ``->`` [[[SYSTEM]]] ``->`` err viewer
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

The command template (with ``\%(job_id)s`` substitution) for testing
the run time stderr viewer functionality for this batch system.


[test battery] ``->`` [[batch systems]] ``->`` [[[SYSTEM]]] ``->`` out viewer
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

The command template (with ``\%(job_id)s`` substitution) for testing
the run time stdout viewer functionality for this batch system.


[test battery] ``->`` [[batch systems]] ``->`` [[[SYSTEM]]] ``->`` [[[[directives]]]]
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

The minimum set of directives that must be supplied to the batch system on the
site to initiate jobs for the tests.


[cylc]
------

Default values for entries in the suite.rc ``[cylc]`` section.


.. _SiteUTCMode:

[cylc] ``->`` UTC mode
^^^^^^^^^^^^^^^^^^^^^^

Allows you to set a default value for UTC mode in a suite at the site level.
See :ref:`UTC-mode` for details.


[cylc] ``->`` health check interval
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Site default suite health check interval.
See :ref:`health-check-interval` for details.


[cylc] ``->`` task event mail interval
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Site default task event mail interval.
See :ref:`task-event-mail-interval` for details.


.. _SiteCylcHooks:

[cylc] ``->`` [[events]]
^^^^^^^^^^^^^^^^^^^^^^^^

You can define site defaults for each of the following options, details
of which can be found under :ref:`SuiteEventHandling`:


[cylc] ``->`` [[events]] ``->`` handlers
""""""""""""""""""""""""""""""""""""""""


[cylc] ``->`` [[events]] ``->`` handler events
""""""""""""""""""""""""""""""""""""""""""""""


[cylc] ``->`` [[events]] ``->`` startup handler
"""""""""""""""""""""""""""""""""""""""""""""""


[cylc] ``->`` [[events]] ``->`` shutdown handler
""""""""""""""""""""""""""""""""""""""""""""""""


[cylc] ``->`` [[events]] ``->`` aborted handler
""""""""""""""""""""""""""""""""""""""""""""""""


[cylc] ``->`` [[events]] ``->`` mail events
"""""""""""""""""""""""""""""""""""""""""""


[cylc] ``->`` [[events]] ``->`` mail footer
"""""""""""""""""""""""""""""""""""""""""""


[cylc] ``->`` [[events]] ``->`` mail from
"""""""""""""""""""""""""""""""""""""""""


[cylc] ``->`` [[events]] ``->`` mail smtp
"""""""""""""""""""""""""""""""""""""""""


[cylc] ``->`` [[events]] ``->`` mail to
"""""""""""""""""""""""""""""""""""""""


[cylc] ``->`` [[events]] ``->`` timeout handler
"""""""""""""""""""""""""""""""""""""""""""""""


[cylc] ``->`` [[events]] ``->`` timeout
"""""""""""""""""""""""""""""""""""""""


[cylc] ``->`` [[events]] ``->`` abort on timeout
""""""""""""""""""""""""""""""""""""""""""""""""


[cylc] ``->`` [[events]] ``->`` stalled handler
"""""""""""""""""""""""""""""""""""""""""""""""


[cylc] ``->`` [[events]] ``->`` abort on stalled
""""""""""""""""""""""""""""""""""""""""""""""""


[cylc] ``->`` [[events]] ``->`` inactivity handler
""""""""""""""""""""""""""""""""""""""""""""""""""


[cylc] ``->`` [[events]] ``->`` inactivity
""""""""""""""""""""""""""""""""""""""""""


[cylc] ``->`` [[events]] ``->`` abort on inactivity
"""""""""""""""""""""""""""""""""""""""""""""""""""


.. _GlobalAuth:

[authentication]
----------------

Authentication of client programs with suite server programs can be configured
here, and overridden in suites if necessary (see :ref:`SuiteAuth`).

The suite-specific passphrase must be installed on a user's account to
authorize full control privileges (see :ref:`tutPassphrases`
and :ref:`ConnectionAuthentication`). In the future we plan to move to a more
traditional user account model so that each authorized user can have their own
password.


[authentication] ``->`` public
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This sets the client privilege level for public access - i.e. no
suite passphrase required.

- *type*: string (must be one of the following options)
- *options*:

  - *identity* - only suite and owner names revealed
  - *description* - identity plus suite title and description
  - *state-totals* - identity, description, and task state totals
  - *full-read* - full read-only access for monitor and GUI
  - *shutdown* - full read access plus shutdown, but no other
    control.

- *default*: state-totals
