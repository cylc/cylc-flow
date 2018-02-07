# Selected Cylc Changes

For the full list of all changes for each release see [closed
milestones](https://github.com/cylc/cylc/milestones?state=closed).

-------------------------------------------------------------------------------
## __cylc-7.6.0 (2018-02-07)__

### Enhancements

[#2373](https://github.com/cylc/cylc/pull/2373) - refactored suite server code
(for efficiency, maintainability, etc.)

[#2396](https://github.com/cylc/cylc/pull/2396) - improved task polling and
state reset:
 * allow polling of finished tasks - to confirm they really succeeded or failed
 * poll to confirm a task message that implies a state reversal - it could just
   be a delayed message
 * allow reset to submitted or running states
 * removed the "enable resurrection" setting - any task can now return from the
   dead

[#2410](https://github.com/cylc/cylc/pull/2410) - new CUSTOM severity task
messages that can trigger a custom event handler

[#2420](https://github.com/cylc/cylc/pull/2420) - <code>cylc monitor</code> now
reconnects automatically if its target suite gets restarted on a different port

[#2430](https://github.com/cylc/cylc/pull/2430) - <code>cylc gscan</code>,
<code>cylc gui</code> - significant reduction in impact on suite server
programs

[#2433](https://github.com/cylc/cylc/pull/2433) - "group" (used to group suites
in <code>cylc gscan</code>) is now defined under the suite "[[meta]]" section

[#2424](https://github.com/cylc/cylc/pull/2424) - task job scripts now run in
<code>bash -l</code> (login shell) instead of explicitly sourcing your
<code>.profile</code> file. <em>WARNING</em>: if you have a
<code>.bash_profile</code> and were using <code>.profile</code>as well just for
Cylc, the latter file will now be ignored because bash gives precendence to the
former. If so, just move your Cylc settings into
</code>.bash_profile</code> or consult the Cylc User Guide for
other ways to configure the task job environment.

[#2441](https://github.com/cylc/cylc/pull/2441) -
[#2458](https://github.com/cylc/cylc/pull/2458) - allow more event handler
arguments:
 * batch system name and job ID
 * submit time, start time, finish time
 * user@host

[#2455](https://github.com/cylc/cylc/pull/2455) - network client improvements:
 * on a failed connection, clients detect if the suite has stopped according to
   the contact file, then report it stopped and remove the contact file
 * on attempt run an already-running suite (contact file exists) print more
   information on how old the suite is and how to shut it down
 * clients running in plain HTTP protocol will no longer attempt to fetch a
   non-existent SSL certificate
 * if a contact file is loaded, always use the values in it to avoid
   conflicting host strings in SSL certificate file, etc. 

[#2468](https://github.com/cylc/cylc/pull/2468) - initialize task remotes
asynchronously via the multiprocessing pool, to avoid holding up suite start-up
unnecessarily. <em>WARNING</em> this introduces new remote commands: <code>cylc
remote-init</code> and <code>cylc remote-tidy</code> that will affect sites
using ssh whitelisting

[#2449](https://github.com/cylc/cylc/pull/2449) -
[#2469](https://github.com/cylc/cylc/pull/2469) -
[#2480](https://github.com/cylc/cylc/pull/2480) -
[#2501](https://github.com/cylc/cylc/pull/2501) -
[#2547](https://github.com/cylc/cylc/pull/2547) -
[#2552](https://github.com/cylc/cylc/pull/2552) -
[#2564](https://github.com/cylc/cylc/pull/2564) -
User Guide:
 * rewrote the section on restart from state checkpoints
 * rewrote the section on suite run databases
 * new section on suite contact files
 * new section on disaster recovery
 * new section on remote monitoring and control
 * improved terminology:
   * "suite server program" instead of "suite daemon" (it's not always a daemon)
   * "severity" instead of "priority" for logging and task messaging
   * "task remote" to encompass the concept of "the account where a task job
     runs" whether under the same user account or not, on another host or not
 * documented requirements for remote access to suite-parsing and
   file-retrieval commands, including via the GUI; and clarified the same for
   suite client commands
 * documented a known bug in use of parameters in complex graph syntax (and an
   easy workaround) - see the task parameters section
 * documented kill-to-hold behavior of tasks with retries configured

[#2475](https://github.com/cylc/cylc/pull/2475) - suite server program:
separate debug mode from daemonization

[#2485](https://github.com/cylc/cylc/pull/2485) - export task job environment
variables on definition and before assignment, to ensure they are available to
subshells immediately - even in expressions inside subsequent variable
definitions

[#2489](https://github.com/cylc/cylc/pull/2489) -
[#2557](https://github.com/cylc/cylc/pull/2557) - 
<code>cylc gscan</code> -
 * configurable menubar visibility at start-up
 * grouped suites now retain their grouped status once stopped

[#2515](https://github.com/cylc/cylc/pull/2515) -
[#2529](https://github.com/cylc/cylc/pull/2529) - 
[#2517](https://github.com/cylc/cylc/pull/2517) -
[#2560](https://github.com/cylc/cylc/pull/2560) - 
<code>cylc gui</code>
 * put prompt dialogss above all windows
 * load new-suite log files after switching to another suite via the File menu
 * graph view: reinstate the right-click menu for ghost nodes (lost at cylc-7.5.0)
 * job log files:
   * fix and document the "extra log files" setting
   * add "view in editor" support for extra log files
   * add text-editor functionality to <code>cylc jobscript</code>
   * add "preview jobscript" functionality to the GUI

[#2527](https://github.com/cylc/cylc/pull/2527) -
[#2431](https://github.com/cylc/cylc/pull/2431) - 
[#2435](https://github.com/cylc/cylc/pull/2435) - 
[#2445](https://github.com/cylc/cylc/pull/2445) - 
[#2491](https://github.com/cylc/cylc/pull/2491) - 
[#2484](https://github.com/cylc/cylc/pull/2484) - 
[#2556](https://github.com/cylc/cylc/pull/2556) - 
improved parameter support: 
 * allow "%d" integer format in parameter templates
 * allow out of range parameter on graph RHS
 * allow positive offset for parameter index on graph
 * allow negative integer parameters
 * allow custom templating of parameter environment variables, in addition to
   the built-in <code>CYLC_TASK_PARAM\_&lt;param-name&gt;</code>
 * allow bare parameter values as task names
 * allow explicit parameter values in "inherit" items under "[runtime]"
 * fix parameters inside (as opposed to beginning or end) of family names
 * fixed inheritance from multiple parameterized namespaces at once

[#2553](https://github.com/cylc/cylc/pull/2553) - upgraded the bundled Jinja2
version to 2.10. This fixes the block scope problem introduced in the previous
version

[#2558](https://github.com/cylc/cylc/pull/2558) - new options to print out JSON
format from <code>cylc show</code> and <code>cylc scan</code>

### Fixes

[#2381](https://github.com/cylc/cylc/pull/2381) - validation: fail bad event
handler argument templates

[#2416](https://github.com/cylc/cylc/pull/2416) - validation: print the problem
namespace in case of bad multiple inheritance

[#2426](https://github.com/cylc/cylc/pull/2426) - validation: fail
non-predefined config item names (e.g. batch scheduler directives) that contain
multiple consecutive spaces (to ensure that hard-to-spot whitespace typos don't
prevent repeated items from overriding as intended)

[#2432](https://github.com/cylc/cylc/pull/2432) - fixed an issue that could
cause HTTPS client failure due to SSL certificate host name mismatch

[#2434](https://github.com/cylc/cylc/pull/2434) - correctly strip "at TIME"
from the end of multi-line task messages

[#2440](https://github.com/cylc/cylc/pull/2440) - <code>cylc suite-state</code>
- fixed DB query of tasks with custom outputs that have not been generated yet

[#2444](https://github.com/cylc/cylc/pull/2444) - added <code>cylc
report-timings</code> to main command help

[#2449](https://github.com/cylc/cylc/pull/2449):
 * server suite and task URLs from suite server programs, rather than parsing
   them from the suite definition - so browsing URLs from a remote GUI now
   works
 * allow proper string templating of suite and task names in URLs; retained the
   old pseudo environment variables for backward compatibility

[#2461](https://github.com/cylc/cylc/pull/2461) - fixed manual task retrigger
after an aborted edit run - this was erroneously using the edited job file 

[#2462](https://github.com/cylc/cylc/pull/2462) - fixed job polling for the SGE
batch scheduler

[#2464](https://github.com/cylc/cylc/pull/2464) - fixed the ssh+HTTPS task
communication method (broken at cylc-7.5.0)

[#2467](https://github.com/cylc/cylc/pull/2467) - fixed an error in reverse
date-time subtraction (first\_point - last\_point)

[#2474](https://github.com/cylc/cylc/pull/2474) - <code>cylc graph</code> -
better handle suite parsing errors on view refresh

[#2496](https://github.com/cylc/cylc/pull/2496) - ensure that broadcasted
environment variables are defined before all user-defined variables, which may
need to reference the broadcasted ones 

[#2523](https://github.com/cylc/cylc/pull/2523) - fixed a problem with suicide
triggers: with several used at once, tasks could go untriggered

[#2546](https://github.com/cylc/cylc/pull/2546) - fixed problems with stop
point after a suite reload: do not reset an existing stop point (this is
dangerous, but it could be done before, and the stop point in the GUI status
bar would still refer to the original)

[#2562](https://github.com/cylc/cylc/pull/2562) - improved advice on how to
generate an initial user config file (<code>global.rc</code>)

-------------------------------------------------------------------------------
## __cylc-7.5.0 (2017-08-29)__

### Enhancements

[#2387](https://github.com/cylc/cylc/pull/2387),
[#2330](https://github.com/cylc/cylc/pull/2330): New suite.rc `[meta]` sections
for suite and task metadata. These hold the existing `title`, `description`,
and `URL` items, plus arbitrary user-defined items. Metadata items can be passed
to event handlers (e.g. a site-specific task "priority" or "importance" rating
could inform an event-handler's decision on whether or not to escalate task
failures).

[#2298](https://github.com/cylc/cylc/pull/2298),
[#2401](https://github.com/cylc/cylc/pull/2401): New shell function
`cylc__job_abort <message>` to abort task job scripts with a custom message
that can be passed to task failed event handlers.

[#2204](https://github.com/cylc/cylc/pull/2204): Remove auto-fallback to HTTP
communications, if HTTPS is not available.  Now HTTP is only used if explicitly
configured.

[#2332](https://github.com/cylc/cylc/pull/2332),
[#2325](https://github.com/cylc/cylc/pull/2325),
[#2321](https://github.com/cylc/cylc/pull/2321),
[#2312](https://github.com/cylc/cylc/pull/2312): Validation efficiency
improvements.

[#2291](https://github.com/cylc/cylc/pull/2291),
[#2303](https://github.com/cylc/cylc/pull/2303),
[#2322](https://github.com/cylc/cylc/pull/2322): Runtime efficiency
improvements.

[#2286](https://github.com/cylc/cylc/pull/2286): New command `cylc
report-timings` to generate reports of task runtime statistics.

[#2304](https://github.com/cylc/cylc/pull/2304): New event handlers for general
CRITICAL events.

[#2244](https://github.com/cylc/cylc/pull/2244), 
[#2258](https://github.com/cylc/cylc/pull/2258): Advanced syntax for excluding
multiple points from cycling sequences.

[#2407](https://github.com/cylc/cylc/pull/2407): Documented exactly how Cylc
uses ssh, scp, and rsync to interact with remote job hosts.

[#2346](https://github.com/cylc/cylc/pull/2346), 
[#2386](https://github.com/cylc/cylc/pull/2386): `cylc graph` now plots
implicit dependences as grayed-out ghost nodes.

[#2343](https://github.com/cylc/cylc/pull/2343): Improved the "Running
Suites" section of the User Guide, including documentation of suite remote
control.

[#2344](https://github.com/cylc/cylc/pull/2344): Attempt to access suite
service files via the filesystem first, before ssh, for other accounts on the
suite host.

[#2360](https://github.com/cylc/cylc/pull/2360): Better validation of suite
parameter configuration.

[#2314](https://github.com/cylc/cylc/pull/2314): In debug mode, send bash job
script xtrace output (from `set -x`) to a separate log file.

### Fixes

[#2409](https://github.com/cylc/cylc/pull/2409): Fixed the `cylc spawn` command
(it was killing tasks, since cylc-7).

[#2378](https://github.com/cylc/cylc/pull/2378): Fixed use of negative offsets
by the `cylc suite-state` command.

[#2364](https://github.com/cylc/cylc/pull/2364): Correctly load completed custom
task outputs on restart.

[#2350](https://github.com/cylc/cylc/pull/2350): Handle bad event handler
command line templates gracefully.

[#2308](https://github.com/cylc/cylc/pull/2308): The parameterized task
environment variable `$CYLC_TASK_PARAM_<param>` is now guaranteed to be defined 
before any use of it in the user-defined task environment section.

[#2296](https://github.com/cylc/cylc/pull/2296): Prevent suites stalling after
a restart that closely follows a warm-start (now the restart, like the warm
start, ignores dependence on tasks from before the warm start point).

[#2295](https://github.com/cylc/cylc/pull/2295): Fixed `cylc cat-log` "open in
editor" functionality for remote job logs.

[#2412](https://github.com/cylc/cylc/pull/2412): Fixed duplication of log
messages to the old log after restart.

-------------------------------------------------------------------------------

## __cylc-7.4.0 (2017-05-16)__

Enhancements and fixes.

### Highlighted Changes

[#2260](https://github.com/cylc/cylc/pull/2260): Open job logs in your text
editor, from CLI (`cylc cat-log`) or GUI.

[#2259](https://github.com/cylc/cylc/pull/2259): `cylc gscan` - various
improvements: right-click menu is now for suite operations only; other items
moved to a main menubar and toolbar (which can be hidden to retain gscan's
popular minimalist look); added all suite stop options (was just the default
clean stop); task-state colour-key popup updates in-place if theme changed; new
collapse/expand-all toobar buttons.

[#2275](https://github.com/cylc/cylc/pull/2275): Pass suite and task URLs to
event handlers.

[#2272](https://github.com/cylc/cylc/pull/2272): Efficiency - reduce memory
footprint.

[#2157](https://github.com/cylc/cylc/pull/2157): 
  * internal efficiency improvements
  * allow reset of individual message outputs
  * "cylc submit" can now submit families

[#2244](https://github.com/cylc/cylc/pull/2244): Graph cycling configuration:
multiple exclusion points.

[#2240](https://github.com/cylc/cylc/pull/2240): Stepped integer parameters.

### Fixes

[#2269](https://github.com/cylc/cylc/pull/2269): Fix auto suite-polling tasks
(i.e. inter-suite dependence graph syntax) - Broken in 7.3.0.

[#2282](https://github.com/cylc/cylc/pull/2282): Fix global config processing
of boolean settings - users could not override a site True setting to False.

[#2279](https://github.com/cylc/cylc/pull/2279): Bundle Jinja2 2.9.6. (up from
2.8) - fixes a known issue with Jinja2 "import with context".

[#2255](https://github.com/cylc/cylc/pull/2255): Fix handling of suite script
items that contain nothing but comments.

[#2247](https://github.com/cylc/cylc/pull/2247): Allow `cylc graph --help`
in the absence of an X environment.

### Other Changes

[#2270](https://github.com/cylc/cylc/pull/2270): Detect and fail null tasks in
graph.

[#2257](https://github.com/cylc/cylc/pull/2257): `cylc gscan` - graceful exit
via Ctrl-C.

[#2252](https://github.com/cylc/cylc/pull/2252): `ssh`: add `-Y` (X Forwarding)
only if necessary.

[#2245](https://github.com/cylc/cylc/pull/2245): SSL certficate: add serial
number (issue number). This allows curl, browsers, etc. to connect to
suite daemons.

[#2265](https://github.com/cylc/cylc/pull/2265): `cylc gpanel` - restored
sorting of items by suite name.

[#2250](https://github.com/cylc/cylc/issues/2250): Updated installation docs
for HTTPS-related requirements.

-------------------------------------------------------------------------------
## __cylc-7.3.0 (2017-04-10)__

New Suite Design Guide, plus other enhancements and fixes.

### Highlighted Changes

[#2211](https://github.com/cylc/cylc/pull/2211): New comprehensive Suite Design
Guide document to replace the outdated Suite Design section in the User Guide.

[#2232](https://github.com/cylc/cylc/pull/2232): `cylc gscan` GUI: stop, hold,
and release suites or groups of suites.

[#2220](https://github.com/cylc/cylc/pull/2220): dummy and simulation mode improvements:
 * new `dummy-local` mode runs dummy tasks as local background jobs (allows
   dummy running other-site suites).
 * proportional run length, if tasks configure an `execution time limit`
 * single common `[simulation]` configuration section for dummy, dummy-local, and
   simulation modes.
 * dummy or simulated tasks can be made to fail at specific cycle points, and
   for first-try only, or all tries.
 * custom message outputs now work in simulation mode as well as the dummy modes.

[#2218](https://github.com/cylc/cylc/pull/2218): fix error trapping in job
scripts (degraded since job file refactoring in 7.1.1)

[#2215](https://github.com/cylc/cylc/pull/2215): SGE batch system support -
fixed formatting of directives with a space in the name.

### Other Notable Changes

[#2233](https://github.com/cylc/cylc/pull/2233): Upgraded the built-in example
suites to cylc-7 syntax.

[#2221](https://github.com/cylc/cylc/pull/2221): `cylc gui` GUI dot view - maintain
user selection during update.

[#2217](https://github.com/cylc/cylc/pull/2217): `cylc gscan` GUI - fix
tracebacks emitted during suite initialization.

[#2219](https://github.com/cylc/cylc/pull/2219): add `user@host` option to
`cylc monitor` an `cylc gui`. Allows suite selection at startup using `cylc
scan` output.

[#2222](https://github.com/cylc/cylc/pull/2222): `cylc gui` GUI graph view -
fixed right-click "view prerequisites" sub-menu.

[#2213](https://github.com/cylc/cylc/pull/2213): Record family inheritance
structure in the run database.

-------------------------------------------------------------------------------
## __cylc-7.2.1 (2017-03-23)__

Minor enhancements and fixes.

### Highlighted Changes

[#2209](https://github.com/cylc/cylc/pull/2209): Fixed the `cylc gui` graph
view, broken at cylc-7.2.0.

[#2193](https://github.com/cylc/cylc/pull/2193): Restored `cylc gscan`
suite-stopped status checkerboard icons, lost at cylc-7.1.1.


[#2208](https://github.com/cylc/cylc/pull/2208): Use suite host name instead
of suite name in the SSL certificate "common name".

[#2206](https://github.com/cylc/cylc/pull/2206): Updated User Guide
installation section.

### Other Notable Changes

[#2191](https://github.com/cylc/cylc/pull/2191): Clearer task prerequisites
print-out.

[#2197](https://github.com/cylc/cylc/pull/2197): Removed the bundled external
OrderedDict package.

[#2194](https://github.com/cylc/cylc/pull/2194): `cylc gscan` - better handling
of suites that are still initializing.

-------------------------------------------------------------------------------
## __cylc-7.2.0 (2017-03-06)__

Minor enhancements and fixes (note mid-level version number bumped up to
reflect significant changes included in 7.1.1 - esp. job file refactoring).

### Highlighted Changes

[#2189](https://github.com/cylc/cylc/pull/2184): New `assert` and
`raise` functions for handling Jinja2 errors in suites.

### Other Changes

[#2186](https://github.com/cylc/cylc/pull/2186): Use lowercase local shell
variable names in new job script shell functions introduced in 7.1.1, to avoid
overriding shell built-ins such as `$HOSTNAME`.

[#2187](https://github.com/cylc/cylc/pull/2187): Fixed a bug causing restart
failure in the presence of an active broadcast of a submission timeout value.

[#2183](https://github.com/cylc/cylc/pull/2183): Use site-configured suite host
self-identification, if present, as hostname in the SSL certificate.

[#2182](https://github.com/cylc/cylc/pull/2182): Fixed failed User Guide build
in 7.1.1.

-------------------------------------------------------------------------------
## __cylc-7.1.1 (2017-02-27)__

Minor enhancements and fixes (plus a significant change: task job file refactoring).

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
