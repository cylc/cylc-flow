# Selected Cylc Changes

For the full list of all changes for each release see [closed
milestones](https://github.com/cylc/cylc/milestones?state=closed).

-------------------------------------------------------------------------------
## __cylc-7.1.1 (2017-02-27)__

Minor enhancements and fixes.

### Highlighted Changes

[#2141](https://github.com/cylc/cylc/pull/2141): Tidier task job files:
hide error trap and messaging code, etc., in external shell functions.

[#2134](https://github.com/cylc/cylc/pull/2134): Suite-state polling (e.g. for
inter-suite triggering) now automatically detects and uses the remote suite
cycle point format.

[#2128](https://github.com/cylc/cylc/pull/2128): Suite-state polling
(e.g. for inter-suite triggering) now works with custom task messages.

[#2172](https://github.com/cylc/cylc/pull/2172): Added a built-in Jinja2 filter
for formatting ISO8601 date-time strings.

[#2164](https://github.com/cylc/cylc/pull/2164): Fixed support for Jinja2 in
site/user config files, broken at 6.11.0.

[#2153](https://github.com/cylc/cylc/pull/2153): `cylc gui` - use task
`execution time limit` as the default mean elapsed time, to compute a progress
bar for the first instance of a cycling task.

[#2154](https://github.com/cylc/cylc/pull/2154): `cylc gui` graph view - fixed
right-click sub-menu activation, broken at 7.1.0.

[#2158](https://github.com/cylc/cylc/pull/2158): `cylc gui` graph view: fix
right-click family ungroup, broken since 7.0.0.

### Other Changes

[#2142](https://github.com/cylc/cylc/pull/2142): New "select all" and "select
none" buttons in the `cylc gui` task filter dialog.

[#2163](https://github.com/cylc/cylc/pull/2163): (Development) New automated
profiling test framework for comparing performance between Cylc versions.

[#2160](https://github.com/cylc/cylc/pull/2160): Better suite stall detection
in the presence of clock-triggered tasks.

[#2156](https://github.com/cylc/cylc/pull/2156): Fix potential division-by-zero
error in `cylc gscan`.

[#2149](https://github.com/cylc/cylc/pull/2149): Fix handling of cycle point
offsets in weeks (e.g. "P1W").

[#2146](https://github.com/cylc/cylc/pull/2146): Documented how to set multiple 
`-l VALUE` directives in jobs submitted to PBS.

[#2129](https://github.com/cylc/cylc/pull/2129): Allow initial cycle point to be
specified on the command line for all relevant commands, if not specified in the
suite definition.

[#2139](https://github.com/cylc/cylc/pull/2139): Fixed error in use of
`execution time limit` in jobs submitted to Platform LSF.

[#2176](https://github.com/cylc/cylc/pull/2176): `cylc gui` graph view - fixed
a bug that could cause a blank graph view window, since 7.0.0. 

[#2161](https://github.com/cylc/cylc/pull/2161): `gcylc gui`- disallow
insertion at cycle points that are not valid for the task (unless overridden
with `--no-check`).

-------------------------------------------------------------------------------
## __cylc-7.1.0 (2017-01-26)__

Minor enhancements and fixes.

### Highlighted Changes

[#2021](https://github.com/cylc/cylc/pull/2021): New command `cylc checkpoint`
to create a named suite state checkpoint that you can restart from.

[#2124](https://github.com/cylc/cylc/pull/2124): open another GUI window (to
view another suite) via the gcylc File menu.

[#2100](https://github.com/cylc/cylc/pull/2100): group multiple task event
notifications into a single email over a 5 minute interval (configurable).

[#2112](https://github.com/cylc/cylc/pull/2112): broadcast settings can now be
loaded (or cancelled) from a file as well as the command line.

[#2096](https://github.com/cylc/cylc/pull/2096): the `cylc gscan` GUI can now
display summary states for suites owned by others.

### Other Changes

[#2126](https://github.com/cylc/cylc/pull/2126): fixed occasional
misidentification of suite stall when only succeeded tasks exist just prior to
shutdown.

[#2127](https://github.com/cylc/cylc/pull/2127): fixed the `cylc diff` command
(broken at 7.0.0)

[#2119](https://github.com/cylc/cylc/pull/2119): fixed remote job kill after a
suite definition reload, for task proxies that exist at the time of the reload.

[#2025](https://github.com/cylc/cylc/pull/2025): GUI right-click menu items can
now be selected with either mouse button 1 or 3.

[#2117](https://github.com/cylc/cylc/pull/2117): improved logic for adding
`lib/cylc` to Python `sys.path` (there was one reported instance of the
system-level `cherrpy` being imported instead of the Cylc-bundled one, in
cylc-7.0.0).

[#2114](https://github.com/cylc/cylc/pull/2114): documented syntax-driven line
continuation in suite graph configuration.

[#2116](https://github.com/cylc/cylc/pull/2116): corrected a rare edge-case
side-effect of manual task-state reset.

[#2107](https://github.com/cylc/cylc/pull/2107): `cylc insert` - disallow
insertion at cycle points that are not valid for the task (unless overridden
with `--no-check`).

[#2106](https://github.com/cylc/cylc/pull/2106): fixed `cylc get-config
--python` output formatting, broken since cylc-6.6.0.

[#2097](https://github.com/cylc/cylc/pull/2097): fixed a problem with task host
and owner task proxies reloaded at suite restart (could cause job poll and
kill to fail in some cases, for tasks in this category).

[#2095](https://github.com/cylc/cylc/pull/2095): fixed validation of mixed
deprecated and new suite.rc syntax.

## __cylc-7.0.0 (2016-12-21)__

**cylc-7 client/server communications is not backward compatible with cylc-6.**

Note that cylc-7 bug fixes were back-ported to a series of 6.11.x releases,
for those who have not transitioned to cylc-7 yet.

### Highlighted Changes

[#1923](https://github.com/cylc/cylc/pull/1923): **A new HTTPS communications
layer, replaces Pyro-3 Object RPC for all client-server communications.**
Suite daemons are now web servers!

[#2063](https://github.com/cylc/cylc/pull/2063): **Removed deprecated cylc-5
syntax and features.**

[#2044](https://github.com/cylc/cylc/pull/2044): Suite start-up now aborts with
a sensible message on suite configuration errors (previously this happened post
daemonization so the user had to check suite logs to see the error).

[#2067](https://github.com/cylc/cylc/pull/2067): Consolidated suite service
files (passphrase, SSL files, contact file, etc.) under `.service/` in the
suite run directory; the suite registration database and port files under
`$HOME/.cylc/` are no longer used; suites can now be grouped in sub-directory
trees under the top level run directory.

[#2033](https://github.com/cylc/cylc/pull/2033): Allow restart from suite state
checkpoints other than the latest (checkpoints are also recorded automatically
before and after restarts, and on reload).

[#2024](https://github.com/cylc/cylc/pull/2024): `cylc gscan` now supports
collapsible suite groups via a top level suite config `group` item.
Right-click *View Column* "Group".

[#2074](https://github.com/cylc/cylc/pull/2074): Task retry states and timers,
and poll timers, now persist across suite restarts. Waiting tasks are not
put in the held state before shutdown. Held tasks are not automatically
released on restart.

[#2004](https://github.com/cylc/cylc/pull/2004): Task event handlers are
now continued on restart.

### Other Changes

[#2042](https://github.com/cylc/cylc/pull/2042): Documented `[scheduling]spawn
to max active cycle points` (new in 6.11.0), which lets successive instances of
the same task run out of order if dependencies allow.

[#2092](https://github.com/cylc/cylc/pull/2092): New command `cylc
get-suite-contact` to print suite contact information (host, port, PID, etc.)

[#2089](https://github.com/cylc/cylc/pull/2089): Improved documentation on
cycling workflows and use of parameterized tasks as a proxy for cycling.

[#2021](https://github.com/cylc/cylc/pull/2021): `cylc gui`: removed the
"connection failed" warning dialog that popped up on suite shutdown. This
should be obvious by the reconnection countdown timer in the info bar.

[#2023](https://github.com/cylc/cylc/pull/2023): New custom event email footer
via global or suite config.

[#2013](https://github.com/cylc/cylc/pull/2013): Fixed "remove task after
spawning" which since 6.9.0 would not force a waiting task to spawn its
successor.

[#2071](https://github.com/cylc/cylc/pull/2071): Fix quote stripping on
`initial cycle point = "now"`.

[#2070](https://github.com/cylc/cylc/pull/2070): Fix dummy mode support for
custom task outputs: they were incorrectly propagated to other tasks.

[#2065](https://github.com/cylc/cylc/pull/2065): `cylc gscan` now supports
suite name filtering via a `--name` command line option.

[#2060](https://github.com/cylc/cylc/pull/2060): 5-second timeout if hanging
connections are encountered during port scanning.

[#2055](https://github.com/cylc/cylc/pull/2055): Task elapsed times now persist
over restarts.

[#2046](https://github.com/cylc/cylc/pull/2046): Multi-task interface for `cylc
show`. Fixed *View Prerequisites* for tasks in the runahead pool.

[#2049](https://github.com/cylc/cylc/pull/2049): Per-host job submission and
execution polling intervals via global/user config files.

[#2051](https://github.com/cylc/cylc/pull/2051): Bundle Jinja2 2.8 with Cylc -
one less external software dependency.

[#2088](https://github.com/cylc/cylc/pull/2088): Support dependence on absolute
cycle points in cycling graphs.

## __cylc-6.11.4 (2017-01-26)__

More bug fixes backported from early Cylc-7 releases.

[#2120](https://github.com/cylc/cylc/pull/2120): fixed remote job kill after a
+suite definition reload, for task proxies that exist at the time of the reload.

[#2111](https://github.com/cylc/cylc/pull/2111): fixed member-expansion of
complex `(FAMILY:fail-any & FAMILYI:finish-all)` graph triggers.

[#2102](https://github.com/cylc/cylc/pull/2102): fixed validation of mixed
deprecated and new suite.rc syntax.

[#2098](https://github.com/cylc/cylc/pull/2098): fixed a problem with task host
and owner task proxies reloaded at suite restart (could cause job poll and
kill to fail in some cases, for tasks in this category).


## __cylc-6.11.3 (2016-12-21)__

One minor bug fix on top of 6.11.2.

[#2091](https://github.com/cylc/cylc/pull/2091): Since 6.11.0 use of cylc-5
special "cold start tasks" caused downstream tasks to become immortal. This
fixes the problem, but note that you should no longer be using this deprecated
feature (which will be removed from cylc-7).


## __cylc-6.11.2 (2016-10-19)__

Some minor enhancements and fixes.

### Highlighted Changes

[#2034](https://github.com/cylc/cylc/pull/2034): Allow restart from checkpoints.
These are currently created before and after reloads, and on restart. (Note that 
since 6.11.0 suite state dump files no longer exist).

[#2047](https://github.com/cylc/cylc/pull/2047): Documented the new
"[scheduling]spawn to max active cycle points" suite configuration item,
which allows successive instances of the same task to run out of order if the
opportunity arises. 

[#2048](https://github.com/cylc/cylc/pull/2048): Allow "view prerequisites" for
tasks in the 'runahead' state.

[#2025](https://github.com/cylc/cylc/pull/2025): Provide a configurable event
mail footer (suite or site/user configuration).

[#2032](https://github.com/cylc/cylc/pull/2032): <code>cylc gui</code> -
removed the annoying warning dialog for connection failed. Take note of the
connection countdown in the status bar instead.

### Other Changes

[#2016](https://github.com/cylc/cylc/pull/2016): Fixed a Python traceback
occasionally generated by the gcylc GUI log view window.

[#2018](https://github.com/cylc/cylc/pull/2018): Restored the incremental
printing of dots to stdout from the <code>cylc suite-state</code> polling
command (lost at 6.11.1).

[#2014](https://github.com/cylc/cylc/pull/2014): Fixed "remove after spawning".
Since 6.9.0 this would not force-spawn the successor of a waiting task.

[#2031](https://github.com/cylc/cylc/pull/2031): <code>cylc gscan</code> -
fixed occasional jumping status icons introduced in 6.11.1.

[#2040](https://github.com/cylc/cylc/pull/2040): Corrected documentation for
the <code>cylc cat-log</code> command (it was using the alias <code>cylc
log</code>).


## __cylc-6.11.1 (2016-09-22)__

Three minor bug fixes on top of 6.11.0:

[#2002](https://github.com/cylc/cylc/pull/2002): fix a bug in the graph string 
parser - if a task appears both with and without a cycle point offset in the 
same conditional trigger expression (unlikely, but possible!)

[#2007](https://github.com/cylc/cylc/pull/2007): fix handling of OS Error if
the user run into the limit for number of forked processes.

[#2008](https://github.com/cylc/cylc/pull/2008): fix occasional traceback from
`cylc gsan`.



## __cylc-6.11.0 (2016-09-13)__

### Highlighted Changes

[#1953](https://github.com/cylc/cylc/pull/1953): Parameterized tasks: generate
tasks automatically without using messy Jinja2 loops.

[#1929](https://github.com/cylc/cylc/pull/1929): Under `[runtime]`:
 * New task `[[[job]]]` sub-sections unify the various batch system, job
   execution, and job polling settings (older settings deprecated).
 * A new `[[[job]]] execution time limit` setting allows cylc to:
    * automatically generate batch system time limit directives;
    * run background or at jobs with the `timeout` command;
    * poll job with configurable delays (default 1, 3, 10 minutes) after
      reaching the time limit.
 * Moved the content of the old `[event hooks]` section to a unified `[events]`
   section (older settings deprecated).

[#1884](https://github.com/cylc/cylc/pull/1884): `cylc gscan` displays a new
warning icon with a tool-tip summary of recent task failures.

[#1877](https://github.com/cylc/cylc/pull/1877): The `gcylc` status bar now
shows a countdown to the next suite connection attempt, and resets the
connection timer schedule if the user changes view settings.

[#1966](https://github.com/cylc/cylc/pull/1966): Optionally spawn waiting tasks
out to "max active cycle points" instead of one cycle point ahead. This means
successive instances of the same task can run out of order (dependencies
allowing).  Use with caution on large suites with a lot of runahead.

[#1940](https://github.com/cylc/cylc/pull/1940): Bash tab completion for cylc
commands.

### Other Changes

[#1585](https://github.com/cylc/cylc/pull/1585): If a suite stalls, report any
unsatisified task prerequisites that cannot be met.

[#1944](https://github.com/cylc/cylc/pull/1944): `cylc get-config` now returns
a valid suite definition.

[#1875](https://github.com/cylc/cylc/pull/1875): Enabled multiple selection in
the gcylc text tree view.

[#1900](https://github.com/cylc/cylc/pull/1900): Automatically continue graph
string lines that end in (or start with) a dependency arrow.

[#1862](https://github.com/cylc/cylc/pull/1862): New notation for initial and
final cycle point in graph cycling section headings.  E.g. `[[[R1/^+PT1H]]]`
means "run once, one hour after the initial cycle point"; `[[[R1/$-PT1H]]]`
means "run once, one hour before the final cycle point".

[#1928](https://github.com/cylc/cylc/pull/1928): New notation for excluding a
cycle point from a recurrence expression, e.g. `[[[T00!^]]]` means 
"daily at T00 after but not including the initial cycle point".

[#1958](https://github.com/cylc/cylc/pull/1958): Suite daemon logging upgrade:
improved log file formatting; the log, out, and err files are now rolled over
together as soon as any one reaches the size limit.

[#1827](https://github.com/cylc/cylc/pull/1827): Suite state dump files no
longer exist - the suite run DB now records all restart information.

[#1912](https://github.com/cylc/cylc/pull/1912): Fixed coloured `cylc scan -c`
output (broken at 6.10.1).

[#1921](https://github.com/cylc/cylc/pull/1921): Don't ignore dependencies
among tasks back-inserted prior to a warm-start cycle point.

[#1910](https://github.com/cylc/cylc/pull/1910): Task job scripts now use `set
-o pipefail` to ensure that failure of any part of a shell pipeline causes a
job failure.

[#1886](https://github.com/cylc/cylc/pull/1886): When a job is submitted for
the first time, any job logs with higher submit numbers will be removed (
these must have been generated by a previous suite run).

[#1946](https://github.com/cylc/cylc/pull/1946): Removed annoying warnings
that "self-suicide is not recommended".

[#1889](https://github.com/cylc/cylc/pull/1889): Record any unhandled task
messages (e.g. general progress messages) in the suite DB.

[#1899](https://github.com/cylc/cylc/pull/1899): Custom task output messages
(for message triggers) are now automatically faked in dummy mode.

-------------------------------------------------------------------------------

## __cylc-6.10.2 (2016-06-02)__

### Highlighted Changes

[#1848](https://github.com/cylc/cylc/pull/1848): Automatic stalled-suite
detection, a "stalled" event hook, and an option to abort (shutdown) if stalled.

[#1850](https://github.com/cylc/cylc/pull/1850): Much reduced CPU loading in
cycling suites that have progressed far beyond their initial cycle point (cache
recent points to avoid continually iterating from the start).

[#1836](https://github.com/cylc/cylc/pull/1836): New `gscan.rc` file to
configure the initial state of `cylc gpanel` and `cylc gscan` (e.g. which
columns to display).

[#1849](https://github.com/cylc/cylc/pull/1849): New configuration options for
the `gcylc` GUI, e.g. to set the initial window size.


### Other Changes

[#1863](https://github.com/cylc/cylc/pull/1863): Report tasks added or removed
by a suite reload.

[#1844](https://github.com/cylc/cylc/pull/1844): Allow client commands from
another suite's task (these would previously load the passphrase for the parent
suite rather than the target suite).

[#1866](https://github.com/cylc/cylc/pull/1866): Allow explicitly unset
intervals in cylc config files, e.g. `execution timeout = # (nothing)`.

[#1863](https://github.com/cylc/cylc/pull/1863): Fixed a recent bug (since in
6.10.0) causing shutdown on reload of a suite after removing a task and its
runtime definition.

[#1864](https://github.com/cylc/cylc/pull/): Stronger checks to prevent users 
starting a second instance of a suite that is already running.

[#1869](https://github.com/cylc/cylc/pull/1869): Fixed day-of-week cycling.

[#1858](https://github.com/cylc/cylc/pull/1858): Fixed a recent bug (since
6.10.1) that could prevent a task at suite start-up from submitting even though
its prerequisites were satisfied.

[#1855](https://github.com/cylc/cylc/pull/1855): Allow inserted tasks to be
released to the `waiting` immediately, even if the suite is currently quiet.

[#1854](https://github.com/cylc/cylc/pull/): Restore wildcards to allow 
insertion of multiple tasks at once (inadvertently disallowed at 6.10.0). 

[#1853](https://github.com/cylc/cylc/pull/1853): Fixed a recent bug (since
6.10.1): reset task outputs to incomplete on manually retriggering or resetting
to a pre-run state.

-------------------------------------------------------------------------------

## __cylc-6.10.1 (2016-05-17)__

### Highlighted Changes

[#1839](https://github.com/cylc/cylc/pull/1839): `gcylc` - fix for occasional
locked-up blank GUI window at start-up (since 6.8.0, Jan 2016).

[#1841](https://github.com/cylc/cylc/pull/1841): `gcylc` tree view - fix for
excessive CPU load when displaying large suites (since 6.10.0).

[#1838](https://github.com/cylc/cylc/pull/1838): Fix for the suite timeout
event timer not resetting on task activity (since 6.10.0).

### Other Changes

[#1835](https://github.com/cylc/cylc/pull/1835): Suite reload - reload all
tasks at once (previously, current active tasks were reloaded only when they
finished, which could result in reloads appearing to take a long time).

[#1833](https://github.com/cylc/cylc/pull/1833): `gcylc` - initial task state
filtering configurable via the  `gcylc.rc` config file.

[#1826](https://github.com/cylc/cylc/pull/1826): Prevent tasks becoming immune
to change by suite reload after being orphaned by one reload (i.e. removed from
the suite) then re-inserted after another.

[#1804](https://github.com/cylc/cylc/pull/1804): PBS job name length - truncate
to 15 characters by default, but can now be configured in `global.rc` for PBS
13+, which supports longer names.

-------------------------------------------------------------------------------

## __cylc-6.10.0 (2016-05-04)__

### Highlighted Changes

[#1769](https://github.com/cylc/cylc/pull/1769),
[#1809](https://github.com/cylc/cylc/pull/1809),
[#1810](https://github.com/cylc/cylc/pull/1810),
[#1811](https://github.com/cylc/cylc/pull/1811),
[#1812](https://github.com/cylc/cylc/pull/1812),
[#1813](https://github.com/cylc/cylc/pull/1813),
[#1819](https://github.com/cylc/cylc/pull/1819): Suite daemon efficiency
and memory footprint - significant improvements!

[#1777](https://github.com/cylc/cylc/pull/1777): Faster validation of
suites with large inter-dependent families.  See also
[#1791](https://github.com/cylc/cylc/pull/1791).

[#1743](https://github.com/cylc/cylc/pull/1743): Improved event handling:
flexible handlers, built-in email handlers, execute event handlers
asynchronously, general suite event handlers.

[#1729](https://github.com/cylc/cylc/pull/1729): `gcylc` - The *File -> Open*
dialog can now connect to suites running on other scanned hosts.

[#1821](https://github.com/cylc/cylc/pull/1821): Right-click on a cycle-point
in the `gcylc` text tree view to operate on all tasks at that cycle point.

### Other Changes

[#1714](https://github.com/cylc/cylc/pull/1714): Further improvements to Jinja2
error reporting.

[#1755](https://github.com/cylc/cylc/pull/1755): Pyro-3.16 is now packaged with
with cylc and has been modified to reduce the overhead of repeated calls to
`socket.gethost*`. We will eventually replace it with a new client/server
communications layer.

[#1807](https://github.com/cylc/cylc/pull/1807): Dropped support for
_detaching_ (or _manual completion_) tasks.

[#1805](https://github.com/cylc/cylc/pull/1805): `gcylc` - corrected the suite
hold/release button state during  active suite reloads.

[#1802](https://github.com/cylc/cylc/pull/1802): Do not unregister running
suites or assume that the argument of `cylc unregister` is a pattern.

[#1800](https://github.com/cylc/cylc/pull/1800): Print a sensible error message
for a suite graph section with a zero-width cycling interval.

[#1791](https://github.com/cylc/cylc/pull/1791): Documented how to write suites
with efficient inter-family triggering.

[#1789](https://github.com/cylc/cylc/pull/1789): Fixed a bug causing high CPU
load in large suites with `queued` tasks present.

[#1788](https://github.com/cylc/cylc/pull/1788): Fixed a bug that could
occasionally result in missing entries in suite run databases.

[#1784](https://github.com/cylc/cylc/pull/1784): Corrected and improved the
advice printed at start-up on how to see if a suite is still running.

[#1781](https://github.com/cylc/cylc/pull/1781): Fixed a bug that could disable
the right-click menu for some tasks after enabling a filter.

[#1768](https://github.com/cylc/cylc/pull/1768): Client commands like `cylc
broadcast` can now be invoked by tasks on remote hosts that do not share a
filesystem with the suite host.

[#1763](https://github.com/cylc/cylc/pull/1763): Remote tasks now load 
the right suite passphrase even if a locally registered suite has
the same name.

[#1762](https://github.com/cylc/cylc/pull/1762): Fixed polling of jobs
submitted to loadleveler (broken since 6.8.1).

[#1816](https://github.com/cylc/cylc/pull/1819),
[#1779](https://github.com/cylc/cylc/pull/1779): Allow task names that contain
family names after a hyphen.

-------------------------------------------------------------------------------

#### For changes prior to cylc-6.10.0 see doc/changes.html in the cylc source tree.
