# Selected Cylc Changes

For the full list of all changes for each release see [closed
milestones](https://github.com/cylc/cylc/milestones?state=closed).

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
