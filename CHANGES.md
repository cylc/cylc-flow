# Selected Cylc Changes

Internal changes that do not directly affect users may not be listed here.  For
all changes see the [closed
milestones](https://github.com/cylc/cylc-flow/milestones?state=closed) for each
release.

-------------------------------------------------------------------------------
## SECURITY NOTE

*[Jinja2 CVE-2019-8341 (High)](https://nvd.nist.gov/vuln/detail/CVE-2019-8341)
An issue was discovered in Jinja2 2.10. The `from_string` function is prone to
Server Side Template Injection (SSTI) where it takes the "source" parameter as
a template object, renders it, and then returns it. The attacker can exploit it
with `{{INJECTION COMMANDS}}` in a URI*

cylc-7.8.x (which supports Python 2.6 and 2.7 bundles Jinja2 2.10. But **this
CVE does not impact cylc-7 because Cylc workflow definitions are not web pages**.

cylc-7.9.x (which requires Python 2.7) bundles Jinja2 2.11.

cylc-8 (master branch, Python 3 - not yet released) uses proper Python package
management and does not bundle Jinja2.

## __cylc-7.8.14 (Upcoming)__


## __cylc-7.8.13 (2023-06-13)__

[#5309](https://github.com/cylc/cylc-flow/pull/5309) - Cylc 8 compat for Cylc Review: 
  - Allow Cylc Review to see all jobs with different flow nums for Cylc 8.1 workflows
  - Warn that not all jobs for different flows will be visible for Cylc 8.0 workflows


## __cylc-7.8.12 (2022-09-30)__

### Fixes

[#5140](https://github.com/cylc/cylc-flow/pull/5140) - Update Cylc Review with
version log files. Fix database error by switching call to a file check.

[#5132](https://github.com/cylc/cylc-flow/pull/5132) - Updates rsync command
to make it compatible with latest (and patched older) rsync releases.

[#5016](https://github.com/cylc/cylc-flow/pull/5016) - fix bug where
polling failure on restart would cause Cylc to assume task is running.

[#4838](https://github.com/cylc/cylc-flow/pull/4838) - fix bug where Cylc 7
would still be able to run a `suite.rc` workflow previously run with Cylc 8.

[#4897](https://github.com/cylc/cylc-flow/pull/4897) - In Cylc Review task jobs
view: Only allow filtering by Cylc 8 task states for Cylc 8 workflows.

## __cylc-7.8.11 (2022-03-07)__

### Fixes

[#4518](https://github.com/cylc/cylc-flow/pull/4518) - load suite contact info
for custom settings for task messaging.

[#4444](https://github.com/cylc/cylc-flow/pull/4444) - cylc review: syntax
highlight all .cylc files (Cylc 8 log directory compatibility).

[#4656](https://github.com/cylc/cylc-flow/pull/4456) - cylc review: display
Rose Bunch logs correctly.


## __cylc-7.8.10 (2021-10-01)__

### Fixes

[#4429](https://github.com/cylc/cylc-flow/pull/4429) - cylc review: handle
log files with names changed at Cylc 8.

[#4437](https://github.com/cylc/cylc-flow/pull/4437) - fix for slow polling
generating an incorrect submit-failed result.


-------------------------------------------------------------------------------
## __cylc-7.8.9 (2021-09-23)__

### Enhancements

[#4264](https://github.com/cylc/cylc-flow/pull/4264) - Syntax highlighting
for Cylc 8 `flow.cylc` files in Cylc Review.

[#4320](https://github.com/cylc/cylc-flow/pull/4320) - Prevent Cylc 7 from
trying to run Cylc 8 workflows.

### Fixes

[#4427](https://github.com/cylc/cylc-flow/pull/4427) -
Fix bug when a conditional expression in the graph contains one task name that
is a substring of another.

[#4233](https://github.com/cylc/cylc-flow/pull/4233) - Fix bug in Cylc Review
caused by Cylc 8 workflows (change in terminology from 'suite' to 'workflow').

[#4276](https://github.com/cylc/cylc-flow/pull/4276) - Fix failure to show
certain log files in Cylc Review.

[#4280](https://github.com/cylc/cylc-flow/pull/4280) - Fix failure to show
Cylc 8 workflow status in Cylc Review.

[#4299](https://github.com/cylc/cylc-flow/pull/4299) -
Fix a GUI bug which can cause extra log files to be listed multiple times.

[#4327](https://github.com/cylc/cylc-flow/pull/4327) - Ensure the suite always
restarts using the same time zone as the last `cylc run`.

-------------------------------------------------------------------------------
## __cylc-7.8.8 (2021-03-24)__

### Enhancements

[#4134](https://github.com/cylc/cylc-flow/pull/4134) - Allow Cylc Review
to display information about Cylc 8 workflows.


-------------------------------------------------------------------------------
## __cylc-7.8.7 (2020-12-04)__

### Enhancements

[#3970](https://github.com/cylc/cylc-flow/pull/3970) - Support Slurm
heteregeneous jobs through an artificial "hetjob_<N>_" or "packjob_<N>_"
directive prefix.

[#3784](https://github.com/cylc/cylc-flow/pull/3784) - Deprecate the
`[runtime][X][parameter environment templates]` section and instead allow
templates in `[runtime][X][environment]`.

### Fixes

[#3948](https://github.com/cylc/cylc-flow/pull/3948) - Only write task
event timers to the database when they have changed (reverts behaviour
change in 7.8.6). This corrects last updated timestamps in cylc review and
reduces filesystem load.

[#3759](https://github.com/cylc/cylc-flow/pull/3759) - Fix a bug in the GUI
tree view that could cause tasks to be sorted in the wrong order.

[#3734](https://github.com/cylc/cylc-flow/pull/3734) - Validate XTrigger
labels to prevent runtime bugs when exporting environment variables.

[#3814](https://github.com/cylc/cylc-flow/pull/3814) - Fixes a minor bug in the
auto-restart functionality which caused suites to wait for local jobs running
on *any* host to complete before restarting.

-------------------------------------------------------------------------------
## __cylc-7.8.6 (2020-05-14)__

### Fixes

[#3597](https://github.com/cylc/cylc-flow/pull/3597) - Fix a bug that could
prevent housekeeping of the task_action_timers DB table and cause many warnings
at restart.

[#3603](https://github.com/cylc/cylc-flow/pull/3603) - Fix a bug that prevented
cycle point format conversion by the `cylc suite-state` command and the
`suite_state` xtrigger function, if the target suite used the default format
but downstream command or suite did not.

-------------------------------------------------------------------------------
## __cylc-7.8.5 (2020-04-22)__

### Enhancements

[#3349](https://github.com/cylc/cylc-flow/pull/3349) - new command `cylc
ref-graph` to generate text-format "reference graphs" without PyGTK (back-port
from Python 3 master for Cylc 8).

## Fixes

[#3514](https://github.com/cylc/cylc-flow/pull/3514) - Fix expanded ids
for GScan, preventing that all suites are expanded after a single suite
was expanded in GScan.

[#3526](https://github.com/cylc/cylc-flow/pull/3526) - Fix sorting of
tasks in the tree view. Uses natural order, so that it follows the
order 1, 2, 10, 11, and not 1, 10, 11, 2.

[#3532](https://github.com/cylc/cylc-flow/pull/3532) - Fix job submission to
SLURM when task name has a percent `%` character.

[#3539](https://github.com/cylc/cylc-flow/pull/3539) - Don't warn that a task
was already added to an internal queue, if the queue is the same.

[#3508](https://github.com/cylc/cylc-flow/pull/3508) - Fix list-valued global
config items not defaulting to localhost values.

-------------------------------------------------------------------------------
## __cylc-7.8.4 (2019-09-04)__

Bug fix release.

Selected user-facing changes:

### Enhancements

[#3203](https://github.com/cylc/cylc-flow/pull/3203) - support alternate run
directories, particularly for sub-suites.


[#3303](https://github.com/cylc/cylc-flow/pull/3303) - improve CLI
task-globbing help.

[#3259](https://github.com/cylc/cylc-flow/pull/3259) - sped up suite validation
(which also affects responsiveness of suite controllers during suite startup,
restarts, and reloads).  Impact of the speedup is most noticeable when dealing
with suite configurations that contain tasks with many task outputs.


### Fixes

[#3307](https://github.com/cylc/cylc-flow/pull/3307) - fix a long-standing bug
causing suites to stall some time after reloading a suite definition that
removed tasks from the graph.

[#3285](https://github.com/cylc/cylc-flow/pull/3285) - fix xtrigger
cycle-sequence specificity.

[#3257](https://github.com/cylc/cylc-flow/pull/3257) - leave '%'-escaped string
templates alone in xtrigger arguments.

[#3204](https://github.com/cylc/cylc-flow/pull/3204) - fix restart on
`cylc run --icp=now SUITE` and related, which was broken at 7.8.3.

[#3205](https://github.com/cylc/cylc-flow/pull/3205) - fix output from `cylc
version`, which should return the numerical version string "7.8.4" not
"flow-7.8.4". (Broken since the source repository was renamed to cylc-flow
to align with the new multi-component cylc-8 architecture).

[#3218](https://github.com/cylc/cylc-flow/pull/3218) - fixed typo in the
User Guide custom batch system handler example (`BATCH_SYSTEM_HANDLER` should
be `BATCH_SYS_HANDLER`).

[#3280](https://github.com/cylc/cylc-flow/pull/3280) - Fix log & DB recording
of broadcasts from xtriggers so they register all settings, not just one.

-------------------------------------------------------------------------------
## __cylc-7.8.3 (2019-06-12)__

Minor maintenance release.

Selected user-facing changes:

### Fixes

[#3159](https://github.com/cylc/cylc-flow/pull/3159) - restore compatibility
with Python 2.6 (for those stuck on older systems).

[#3186](https://github.com/cylc/cylc-flow/pull/3186),
[#3183](https://github.com/cylc/cylc-flow/pull/3183) - Fix subprocess
invocation of commands from GUI, e.g. `cylc run` and `cylc trigger-edit`, which
were broken at 7.8.2.

[#3147](https://github.com/cylc/cylc-flow/pull/3147) - Fix restart
correctness when the suite has a hold point, stop point, a stop task, a stop
clock time and/or an auto stop option. These settings are now stored in the
suite run SQLite file and are retrieved on suite restart. In addition, the
settings are removed when they are consumed, e.g. if the suite stopped
previously on rearching the stop point, the stop point would be consumed, so
that on restart the suite would not stop again immediately.

The `cylc run` command can now accept `--initial-cycle-point=CYCLE-POINT`
(`--icp=CYCLE-POINT)` and `--start-cycle-point=CYCLE-POINT` options, as an
alternative to a second command line argument. This is more consistent with
commands such as `cylc validate`, and with the final/stop cycle point options.

After this change:
* `cylc run SUITE POINT` is equivalent to `cylc run --icp=POINT SUITE`.
* `cylc run -w SUITE POINT` is equivalent to `cylc run -w --start-point=POINT SUITE`.

The `cylc run` and `cylc restart` commands can now accept the
`--final-cycle-point=POINT` and `--stop-cycle-point=POINT` options too. The
`--until=POINT` option is now an alias for `--final-cycle-point=POINT` option.

The `cylc run` and `cylc restart` commands can now accept the new
`--auto-shutdown` option. This overrides the equivalent suite configuration to
force auto shutdown to be enabled. Previously, it was only possible to disable
auto shutdown on the command line.

-------------------------------------------------------------------------------
## __cylc-7.8.2 (2019-05-02)__

Maintenance release with minor enhancements.

Selected user-facing changes:

### Enhancements

[#3128](https://github.com/cylc/cylc-flow/pull/3128) - Add security bug
reporting guidelines (`SECURITY.md`)

[#3078](https://github.com/cylc/cylc-flow/pull/3078) - Add an "aborted"
suite event, to support alerting of unexpected suite shutdowns.

[#3017](https://github.com/cylc/cylc-flow/pull/3017) - Document all the parts
of a task job script and how they relate to one another.

[#3002](https://github.com/cylc/cylc-flow/pull/3002) - Make suite context
available to custom Jinja2 filter functions.

[#2992](https://github.com/cylc/cylc-flow/pull/2992) - Fix incorrect time
record in the suite DB on submit failed events.

[#2986](https://github.com/cylc/cylc-flow/pull/2986) - Close GUI cleanly on
Ctrl-C.

[#2970](https://github.com/cylc/cylc-flow/pull/2970) - Generate single- (as
well as multi-) page User Guide under the new (post LaTeX) system.

[#2948](https://github.com/cylc/cylc-flow/pull/2948) - Higher-contrast link
colors in the User Guide.

### Fixes

`cylc review`:
- [#3125](https://github.com/cylc/cylc-flow/pull/3125),
  [#3146](https://github.com/cylc/cylc-flow/pull/3125) -
URL encoding for special characters in suite names.
- [#2938](https://github.com/cylc/cylc-flow/pull/2938) - Restore visibility of
  waiting tasks.
- [#2945](https://github.com/cylc/cylc-flow/pull/2945) - Fix for possible code
  injection vulnerability.

[#3109](https://github.com/cylc/cylc-flow/pull/3109) - Preprend custom
Jinja2 filter locations to the Python search path in case of name clashes with
other modules.

[#3047](https://github.com/cylc/cylc-flow/pull/3047) - Fix `cylc graph`
node styling issues and desktop theme compatibility

[#3053](https://github.com/cylc/cylc-flow/pull/3053) - Prevent batch system
job kill from immediately releasing tasks from retrying status (for tasks
configured to retry on failure).

[#3100](https://github.com/cylc/cylc-flow/pull/3100) - Restore the intended
"kill all active tasks"  behavior of `cylc kill SUITE` with no task glob
argument.

[#3059](https://github.com/cylc/cylc-flow/pull/3059) - Fix suite abort on
referencing a non-existent external trigger function.

[#2968](https://github.com/cylc/cylc-flow/pull/2968) - Fix for job submission
failures after reloading a suite with some tasks in the "retrying" state..

[#2941](https://github.com/cylc/cylc-flow/pull/2941) -
Suite host selection: ignore stdout generated by login scripts.

-------------------------------------------------------------------------------
## __cylc-7.8.1 (2019-01-25)__

Maintenance and minor enhancement release, plus new-format User Guide.

Selected user-facing changes:

### Enhancements

[#2910](https://github.com/cylc/cylc-flow/pull/2910) - replace LaTeX-generated HTML
and PDF User Guide with Sphinx-generated HTML.

[#2815](https://github.com/cylc/cylc-flow/pull/2815) - allow initial cycle point
relative to current time.

[#2902](https://github.com/cylc/cylc-flow/pull/2902) - expose suite UUID to event
handlers.

### Fixes

[#2932](https://github.com/cylc/cylc-flow/pull/2932) - fix possible blocking pipe
due to chatty job submission (and other subprocess) commands.

[#2921](https://github.com/cylc/cylc-flow/pull/2921) - better suite validation
warning for out-of-bounds cycling sequences.

[#2924](https://github.com/cylc/cylc-flow/pull/2924) - fix and expand 7.8.0 `cylc
review` documentation in the User Guide.

-------------------------------------------------------------------------------
## __cylc-7.8.0 (2018-11-27)__

Minor release with over 120 issues closed. Significant issues include:

### Enhancements

[#2693](https://github.com/cylc/cylc-flow/pull/2693) - __auto host selection__; and
[#2809](https://github.com/cylc/cylc-flow/pull/2809) - __auto migration__.
`cylc run` and `cylc restart` can now select the best host (based on several
metrics) on which to launch suite server programs. And running suites
can be told (via global config) to self-migrate to another available host, e.g.
for server maintenance. (The pool of suite hosts should see a shared
filesystem).

[#2614](https://github.com/cylc/cylc-flow/pull/2614) and
[#2821](https://github.com/cylc/cylc-flow/pull/2821) - __web-based job log viewer__ -
 `cylc review` (migration of "Rose Bush" from the Rose project).


[#2339](https://github.com/cylc/cylc-flow/pull/2339) - __general external
triggering__: tasks can trigger off of arbitrary user-defined Python functions
called periodically by the suite server program, with built-in functions
for suite-state (inter-suite) triggering and clock triggering (these
deprecate the existing suite-state polling tasks and clock-triggered tasks).

[#2734](https://github.com/cylc/cylc-flow/pull/2734) - __EmPy templating__
support, as an alternative to Jinja2. _"EmPy allows embedding plain Python code
within templates and doesn't enforce any particular templating philosophy."_

[#2733](https://github.com/cylc/cylc-flow/pull/2733) - enhanced Jinja2 support:
- __import pure Python modules__ in the same way as template modules
- Jinja2Tests and Jinja2Globals, for custom "is" tests and global variables
  (c.f. our existing Jinja2Filters for custom filters).

[#2682](https://github.com/cylc/cylc-flow/pull/2682) - new built-in
Jinja2 filter to convert ISO8601 date-time durations to
decimal seconds or hours.

[#2842](https://github.com/cylc/cylc-flow/pull/2842) - `cylc gui` and
`cylc graph` - better integration with system desktop themes, including dark
themes; and other minor graph visualization improvements.

[#2807](https://github.com/cylc/cylc-flow/pull/2807) - task output events (event
handlers can now be triggered when a task reports a registered output message).

[#2868](https://github.com/cylc/cylc-flow/pull/2868) - a new task
runtime config item `exit-script`, for scripting to be executed at the
last moment after successful job completion. (Companion of `err-script`).

[#2781](https://github.com/cylc/cylc-flow/pull/2781) and
[#2854](https://github.com/cylc/cylc-flow/pull/2854) - improved suite
server program logging (including: `log/suite/err` is no longer used).

[#2849](https://github.com/cylc/cylc-flow/pull/2849) - record local
background jobs by host name rather than "localhost".

[#2877](https://github.com/cylc/cylc-flow/pull/2877) - new batch system
handler `pbs_multi_cluster`, supports PBS 13 clients fronting
heterogeneous clusters with different home directories from the
cylc remote. (Not needed for PBS 14+.) (For Rose suites this requires a
corresponding change to `rose suite-run`:
[metomi/rose#2252](https://github.com/metomi/rose/pull/2252).)

[#2812](https://github.com/cylc/cylc-flow/pull/2812) - `cylc gscan`:
show application menu bar by default.

[#2768](https://github.com/cylc/cylc-flow/pull/2768) - `cylc gscan`: display Cylc
version of running suites.

[#2786](https://github.com/cylc/cylc-flow/pull/2786) - make task try number
available to event handlers (as for task job submit number).

[#2771](https://github.com/cylc/cylc-flow/pull/2771) - bash command completion:
complete suite names for commands that take a suite name argument (see
`etc/cylc-bash-completion`).

[#2769](https://github.com/cylc/cylc-flow/pull/2769) - `cylc check-software` now
takes arguments to check for availability of specific modules.

[#2763](https://github.com/cylc/cylc-flow/pull/2763) - `cylc monitor` - clean exit
on Ctrl-C.

[#2704](https://github.com/cylc/cylc-flow/pull/2704) - paginated `cylc help` output.

[#2660](https://github.com/cylc/cylc-flow/pull/2660) - new `gcylc.rc` config item to
show grouped cyclepoint subgraphs by default.

[#2766](https://github.com/cylc/cylc-flow/pull/2766) - (development) formal test
coverage reporting and integration with GitHub.

[#2751](https://github.com/cylc/cylc-flow/pull/2751) - (development) new contributor
guidelines - see `CONTRIBUTING.md`.

### Fixes

[#2876](https://github.com/cylc/cylc-flow/pull/2876) - avoid subprocess hang when
executing commands that generate a lot of stdout (such as when submitting
hundreds of jobs at once).

[#2828](https://github.com/cylc/cylc-flow/pull/2828) - `suite.rc` - fail validation
on detecting trailing whitespace after a line continuation character.

[#2807](https://github.com/cylc/cylc-flow/pull/2807) - handle multiple events of
the same type with the same message (e.g. warnings) from the same task job.

[#2803](https://github.com/cylc/cylc-flow/pull/2803) - reset job submit number
correctly after aborting (backing out of) a trigger edit-run.

[#2727](https://github.com/cylc/cylc-flow/pull/2727) - `cylc gui`: fix dropdown list
of log numbers for re-inserted tasks or after suite
restart.

[#2759](https://github.com/cylc/cylc-flow/pull/2759) and
[#2816](https://github.com/cylc/cylc-flow/pull/2816) -
suite registration tweaks and fixes.

[#2861](https://github.com/cylc/cylc-flow/pull/2861) - improved emacs
syntax highlighting.

[#2892](https://github.com/cylc/cylc-flow/pull/2892) - print the bad host name along
with "Name or service not known" exceptions.


-------------------------------------------------------------------------------
## __cylc-7.7.2 (2018-07-26)__

Maintenance release.

(Some minor changes not relevant to normal users may be omitted.)

### Fixes and minor enhancements

[#2719](https://github.com/cylc/cylc-flow/pull/2719) - improved job poll logging

[#2724](https://github.com/cylc/cylc-flow/pull/2724) - fix a rare error associated
with ithe use of final cycle point in multiple recurrence expressions

[#2723](https://github.com/cylc/cylc-flow/pull/2723) - fix remote commands (executed
by remote task jobs) running in UTC mode when the suite is not running in UTC
mode

[#2726](https://github.com/cylc/cylc-flow/pull/2726) - fix crash in suites with no
final cycle point that are reloaded following a restart

[#2716](https://github.com/cylc/cylc-flow/pull/2716) - ensure that job polling
interval lists are not overridden

[#2714](https://github.com/cylc/cylc-flow/pull/2714) - block irrelevant
`InsecureRequestWarning`s from urllib3 on anonymous suite server access by
`cylc scan` and `cylc ping`

[#2715](https://github.com/cylc/cylc-flow/pull/2715) - fix a cross-version
incompatibility, if a cylc-7.6.x task job messages a cylc-7.7.1 suite

[#2710](https://github.com/cylc/cylc-flow/pull/2710) - fix a GUI error on
right-clicking a "scissor node" in the graph view

-------------------------------------------------------------------------------
## __cylc-7.7.1 (2018-06-27)__

Minor maintenance release.

### Fixes

(Several minor fixes have been omitted from this list.)

[#2678](https://github.com/cylc/cylc-flow/pull/2678) - fix loading of job poll
timers on restart (bug introduced at last release)

[#2683](https://github.com/cylc/cylc-flow/pull/2683) - fix potential error in
`cylc check-software` (which checks for installed software dependencies)

[#2691](https://github.com/cylc/cylc-flow/pull/2691) PBS support - handle job poll
result correctly if qstat temporarily fails to connect to the server

[#2703](https://github.com/cylc/cylc-flow/pull/2703) - fix an error
(inconsequential) that appears in the suite log at restart: `ValueError: No
JSON object could be decoded`

[#2692](https://github.com/cylc/cylc-flow/pull/2692) - fix X11 forwarding for GUI
edit job log, with `cylc gui --host=HOST`

[#2690](https://github.com/cylc/cylc-flow/pull/2690) - invoking Cylc command help
should not require `$DISPLAY` to be set

[#2677](https://github.com/cylc/cylc-flow/pull/2677) - use random serial numbers in
the self-signed SSL certificates generated by suite server programs

[#2688](https://github.com/cylc/cylc-flow/pull/2688)
[#2705](https://github.com/cylc/cylc-flow/pull/2705) - block several security
warnings emitted by `urllib3` under old Python versions (2.6). *We are
aware of the security issues, but these warnings serve no purpose on affected
platforms except to confuse and annoy users.*

[#2676](https://github.com/cylc/cylc/pull/2676) - use `#!/usr/bin/env python2`
(i.e. Python-2 specific) in Cylc source files, to avoid issues with default
Python 3 installations (note Cylc is going to Python 3 next year)

[#2679](https://github.com/cylc/cylc-flow/pull/2679) - change bold font back to
normal in the GUI log viewer

-------------------------------------------------------------------------------
## __cylc-7.7.0 (2018-05-12)__

### Enhancements

[#2661](https://github.com/cylc/cylc-flow/pull/2661) -
 * new User Guide section on Remote Job Management
 * tidy the installation documentation
 * standardise directory structures (all docs updated accordingly):
   - deprecated `<cylc-dir>conf/` file locations:
     - site config file `<cylc-dir>etc/global.rc`
     - gcylc config example `<cylc-dir>/etc/gcylc.rc.eg`
     - site job environment init `<cylc-dir/etc/job-init-env.sh`
     - editor syntax files in `<cylc-dir>etc/syntax/`
     - bash completion script `<cylc-dir>/etc/cylc-bash-completion`
   - user `global.rc` can now go in `~/.cylc/<cylc-version>/` or `~/.cylc/`
     (the version-specific location avoid forward compatibility problems - see
     notes in `<cylc-dir>/etc/global.rc.eg`).
   - moved central cylc wrapper template to `usr/bin/cylc`
   - various developer scripts and notes moved from `<cylc-dir>/dev/` to
     `<cylc-dir>/etc/dev-bin, dev-notes, dev-suites`.
   - *the ancient `site.rc` and `user.rc` global config filename variants are
     now obsolete.*

[#2659](https://github.com/cylc/cylc-flow/pull/2659) - commands in the process pool
(event handlers, and job submit, poll and kill commands) will now be killed on
a configurable timeout if they hang, rather than tying up a member of the
finite process pool: `global.rc` default: `process pool timeout = PT10M`

[#2582](https://github.com/cylc/cylc-flow/pull/2582) - improve client/server
interface, including: `cylc message` can send multiple messages at once, with
different severities; server ignores messages from superseded job submits;
running jobs detect that the suite has been cold-started under them and will
not attempt to connect; ssh-based indirect client-server communication now
works automatically for all clients, not just messaging.

[#2582](https://github.com/cylc/cylc-flow/pull/2582),
[#2624](https://github.com/cylc/cylc-flow/pull/2624), and earlier changes: all job
host actions are now done by remote `cylc` subcommands that are compatible with
ssh whitelisting.

[#2590](https://github.com/cylc/cylc-flow/pull/2590) - replaced the fixed process
pool with direct management of individual sub-processes (for external commands
executed by the server program).

[#2561](https://github.com/cylc/cylc-flow/pull/2561) - pass resolved triggering
dependencies to `$CYLC_TASK_DEPENDENCIES` in job environments.

[#2639](https://github.com/cylc/cylc-flow/pull/2639) - date-time cycling: document
availability of 365-day (never a leap year) and 366-day (always a leap year)
calendars.

[#2597](https://github.com/cylc/cylc-flow/pull/2597) - emit a "late" event if a task
has not triggered by a user-defined real-time offset relative to cycle point.

[#2648](https://github.com/cylc/cylc-flow/pull/2648) - improve version reporting.
Note than non-standard lowercase `cylc -v` is now gone; use `cylc -V` or `cylc
--version`, with optional `--long` format to print as well as version.

[#2620](https://github.com/cylc/cylc-flow/pull/2620) - re-document the long-dated
`[special tasks]sequential` and recommend using explicit dependencies in the
graph instead.

[#2584](https://github.com/cylc/cylc-flow/pull/2584) - internal queues now release
task jobs on a FIFO (First In, First Out) basis, rather than randomly.

[#2538](https://github.com/cylc/cylc-flow/pull/2538) - remove leading whitespace
from multi-line `script` items in task definitions, for cleaner job scripts.

[#2503](https://github.com/cylc/cylc-flow/pull/2503),
[#2624](https://github.com/cylc/cylc-flow/pull/2624) - `cylc cat-log`: all remote
host actions now done by a `cylc` sub-command; and simpler command options (see
`cylc cat-log --help`; **warning: the old command options are not supported**)

### Fixes

[#2666](https://github.com/cylc/cylc-flow/pull/2666) - `cylc scan`: make default
behavior consistent with `cylc gscan`: get suite information from `~/cylc-run/`
only for the current user; and no partial matches with `-n/--name=PATTERN`
(i.e. `--name=bar` will only match the suite `bar`, not `foobar` or `barbaz`).

[#2593](https://github.com/cylc/cylc-flow/pull/2593) - fix polling after job
execution timeout (configured pre-poll delays were being ignored).

[#2656](https://github.com/cylc/cylc-flow/pull/2656) - fix suicide triggers with
multiple prerequisites in the same graph line.

[#2638](https://github.com/cylc/cylc-flow/pull/2618) - fix duplicate "failed" task
events after `cylc stop --kill`.

[#2653](https://github.com/cylc/cylc-flow/pull/2653) - tidy and correct the main `cylc
help` documentation.

[#2644](https://github.com/cylc/cylc-flow/pull/2644),
[#2646](https://github.com/cylc/cylc-flow/pull/2646) - fix some graph parsing edge
cases.

[#2649](https://github.com/cylc/cylc-flow/pull/2649) - respect suite
UTC mode when recording job submit time (database and GUI tree view).

[#2631](https://github.com/cylc/cylc-flow/pull/2631) - fix "failed" task event after
bad host select.

[#2626](https://github.com/cylc/cylc-flow/pull/2626) - `cylc gui`: fix error when
a task job completes just before "view task prerequisites" (menu) is actioned.

[#2600](https://github.com/cylc/cylc-flow/pull/2600) - correct task prerequisite
manipulation on state changes.

[#2596](https://github.com/cylc/cylc-flow/pull/2596) - fix reference to parameter
values containing `+` or `-` characters.

[#2592](https://github.com/cylc/cylc-flow/pull/2592) - permit syntax errors in edit
runs, so that the job file still gets written.

[#2579](https://github.com/cylc/cylc-flow/pull/2579) - `cylc gscan`: fix a
re-spawning error dialog.

[#2674](https://github.com/cylc/cylc-flow/pull/2674) - `cylc cat-log`: avoid leaving
orphaned tail-follow processes on job hosts.


-------------------------------------------------------------------------------
## __cylc-7.6.1 (2018-03-28)__

A collection of bug fixes made since cylc-7.6.0.

### Fixes

[#2571](https://github.com/cylc/cylc-flow/pull/2571) - `cylc gui`: fix tailing of
remote job logs from the GUI (in 7.6.0 this failed with a Python traceback).

[#2596](https://github.com/cylc/cylc-flow/pull/2596) - allow parameter values that
contain +/- characters

[#2574](https://github.com/cylc/cylc-flow/pull/2574) - `cylc gscan HOST`: show just
the owner's suites by default (at 7.6.0 this showed all suites on HOST).

[#2592](https://github.com/cylc/cylc-flow/pull/2592) - `cylc trigger --edit`:
disable job script syntax checking in edit runs (this prevented a new job
script from being written for editing).

[#2579](https://github.com/cylc/cylc-flow/pull/2579) - `cylc gscan`: fix respawning
error dialog on giving a bad regular expression (on the command line) to match
owner or suite name.

[#2606](https://github.com/cylc/cylc-flow/pull/2606) - jobs with batch system info
missing in a corrupted status file (thus not pollable) will now poll as failed
rather appear stuck as running.

[#2603](https://github.com/cylc/cylc-flow/pull/2603) - `cylc gui` (graph view): fix
possible error on inserting a nested family.

[#2602](https://github.com/cylc/cylc-flow/pull/2602) - `cylc gui` (tree view): fix
negative progress bar value (reportedly possible after manual task state
manipulations).

[#2586](https://github.com/cylc/cylc-flow/pull/2586) - `cylc gui` (tree view): fix
possible division-by-zero error in elapsed time computation.

[#2588](https://github.com/cylc/cylc-flow/pull/2588) - `cylc trigger --edit`: fix
edit runs for tasks with dynamic remote host selection.

[#2585](https://github.com/cylc/cylc-flow/pull/2585) - fix recovery from a failed
host select command.

-------------------------------------------------------------------------------
## __cylc-7.6.0 (2018-02-07)__

### Enhancements

[#2373](https://github.com/cylc/cylc-flow/pull/2373) - refactored suite server code
(for efficiency, maintainability, etc.)

[#2396](https://github.com/cylc/cylc-flow/pull/2396) - improved job polling and task
state reset:
 * allow polling of finished tasks - to confirm they really succeeded or failed
 * poll to confirm a task message that implies a state reversal - it could just
   be a delayed message
 * allow reset to submitted or running states
 * removed the "enable resurrection" setting - any task can now return from the
   dead

[#2410](https://github.com/cylc/cylc-flow/pull/2410) - new CUSTOM severity task
messages that can trigger a custom event handler

[#2420](https://github.com/cylc/cylc-flow/pull/2420) - `cylc monitor` now
reconnects automatically if its target suite gets restarted on a different port

[#2430](https://github.com/cylc/cylc-flow/pull/2430) - `cylc gscan`,
`cylc gui` - significant reduction in impact on suite server
programs

[#2433](https://github.com/cylc/cylc-flow/pull/2433) - "group" (used to group suites
in `cylc gscan`) is now defined under the suite "[[meta]]" section

[#2424](https://github.com/cylc/cylc-flow/pull/2424) - task job scripts now run in
`bash -l` (login shell) instead of explicitly sourcing your
`.profile` file. *WARNING*: if you have a
`.bash_profile` and were using `.profile` as well just for
Cylc, the latter file will now be ignored because bash gives precendence to the
former. If so, just move your Cylc settings into
`.bash_profile` or consult the Cylc User Guide for
other ways to configure the task job environment.

[#2441](https://github.com/cylc/cylc-flow/pull/2441) -
[#2458](https://github.com/cylc/cylc-flow/pull/2458) - allow more event handler
arguments:
 * batch system name and job ID
 * submit time, start time, finish time
 * user@host

[#2455](https://github.com/cylc/cylc-flow/pull/2455) - network client improvements:
 * on a failed connection, clients detect if the suite has stopped according to
   the contact file, then report it stopped and remove the contact file
 * on attempt run an already-running suite (contact file exists) print more
   information on how old the suite is and how to shut it down
 * clients running in plain HTTP protocol will no longer attempt to fetch a
   non-existent SSL certificate
 * if a contact file is loaded, always use the values in it to avoid
   conflicting host strings in SSL certificate file, etc.

[#2468](https://github.com/cylc/cylc-flow/pull/2468) - initialize task remotes
asynchronously via the multiprocessing pool, to avoid holding up suite start-up
unnecessarily. *WARNING* this introduces new remote commands: `cylc
remote-init` and `cylc remote-tidy` that will affect sites
using ssh whitelisting

[#2449](https://github.com/cylc/cylc-flow/pull/2449) -
[#2469](https://github.com/cylc/cylc-flow/pull/2469) -
[#2480](https://github.com/cylc/cylc-flow/pull/2480) -
[#2501](https://github.com/cylc/cylc-flow/pull/2501) -
[#2547](https://github.com/cylc/cylc-flow/pull/2547) -
[#2552](https://github.com/cylc/cylc-flow/pull/2552) -
[#2564](https://github.com/cylc/cylc-flow/pull/2564) -
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

[#2475](https://github.com/cylc/cylc-flow/pull/2475) - suite server program:
separate debug mode from daemonization

[#2485](https://github.com/cylc/cylc-flow/pull/2485) - export task job environment
variables on definition and before assignment, to ensure they are available to
subshells immediately - even in expressions inside subsequent variable
definitions

[#2489](https://github.com/cylc/cylc-flow/pull/2489) -
[#2557](https://github.com/cylc/cylc-flow/pull/2557) -
`cylc gscan` -
 * configurable menubar visibility at start-up
 * grouped suites now retain their grouped status once stopped

[#2515](https://github.com/cylc/cylc-flow/pull/2515) -
[#2529](https://github.com/cylc/cylc-flow/pull/2529) -
[#2517](https://github.com/cylc/cylc-flow/pull/2517) -
[#2560](https://github.com/cylc/cylc-flow/pull/2560) -
`cylc gui`
 * put prompt dialogss above all windows
 * load new-suite log files after switching to another suite via the File menu
 * graph view: reinstate the right-click menu for ghost nodes (lost at cylc-7.5.0)
 * job log files:
   * fix and document the "extra log files" setting
   * add "view in editor" support for extra log files
   * add text-editor functionality to `cylc jobscript`
   * add "preview jobscript" functionality to the GUI

[#2527](https://github.com/cylc/cylc-flow/pull/2527) -
[#2431](https://github.com/cylc/cylc-flow/pull/2431) -
[#2435](https://github.com/cylc/cylc-flow/pull/2435) -
[#2445](https://github.com/cylc/cylc-flow/pull/2445) -
[#2491](https://github.com/cylc/cylc-flow/pull/2491) -
[#2484](https://github.com/cylc/cylc-flow/pull/2484) -
[#2556](https://github.com/cylc/cylc-flow/pull/2556) -
improved parameter support:
 * allow "%d" integer format in parameter templates
 * allow out of range parameter on graph RHS
 * allow positive offset for parameter index on graph
 * allow negative integer parameters
 * allow custom templating of parameter environment variables, in addition to
   the built-in `CYLC_TASK_PARAM\_&lt;param-name&gt;`
 * allow bare parameter values as task names
 * allow explicit parameter values in "inherit" items under "[runtime]"
 * fix parameters inside (as opposed to beginning or end) of family names
 * fixed inheritance from multiple parameterized namespaces at once

[#2553](https://github.com/cylc/cylc-flow/pull/2553) - upgraded the bundled Jinja2
version to 2.10. This fixes the block scope problem introduced in the previous
version

[#2558](https://github.com/cylc/cylc-flow/pull/2558) - new options to print out JSON
format from `cylc show` and `cylc scan`

### Fixes

[#2381](https://github.com/cylc/cylc-flow/pull/2381) - validation: fail bad event
handler argument templates

[#2416](https://github.com/cylc/cylc-flow/pull/2416) - validation: print the problem
namespace in case of bad multiple inheritance

[#2426](https://github.com/cylc/cylc-flow/pull/2426) - validation: fail
non-predefined config item names (e.g. batch scheduler directives) that contain
multiple consecutive spaces (to ensure that hard-to-spot whitespace typos don't
prevent repeated items from overriding as intended)

[#2432](https://github.com/cylc/cylc-flow/pull/2432) - fixed an issue that could
cause HTTPS client failure due to SSL certificate host name mismatch

[#2434](https://github.com/cylc/cylc-flow/pull/2434) - correctly strip "at TIME"
from the end of multi-line task messages

[#2440](https://github.com/cylc/cylc-flow/pull/2440) - `cylc suite-state`
- fixed DB query of tasks with custom outputs that have not been generated yet

[#2444](https://github.com/cylc/cylc-flow/pull/2444) - added `cylc
report-timings` to main command help

[#2449](https://github.com/cylc/cylc-flow/pull/2449):
 * server suite and task URLs from suite server programs, rather than parsing
   them from the suite definition - so browsing URLs from a remote GUI now
   works
 * allow proper string templating of suite and task names in URLs; retained the
   old pseudo environment variables for backward compatibility

[#2461](https://github.com/cylc/cylc-flow/pull/2461) - fixed manual task retrigger
after an aborted edit run - this was erroneously using the edited job file

[#2462](https://github.com/cylc/cylc-flow/pull/2462) - fixed job polling for the SGE
batch scheduler

[#2464](https://github.com/cylc/cylc-flow/pull/2464) - fixed the ssh+HTTPS task
communication method (broken at cylc-7.5.0)

[#2467](https://github.com/cylc/cylc-flow/pull/2467) - fixed an error in reverse
date-time subtraction (first\_point - last\_point)

[#2474](https://github.com/cylc/cylc-flow/pull/2474) - `cylc graph` -
better handle suite parsing errors on view refresh

[#2496](https://github.com/cylc/cylc-flow/pull/2496) - ensure that broadcasted
environment variables are defined before all user-defined variables, which may
need to reference the broadcasted ones

[#2523](https://github.com/cylc/cylc-flow/pull/2523) - fixed a problem with suicide
triggers: with several used at once, tasks could go untriggered

[#2546](https://github.com/cylc/cylc-flow/pull/2546) - fixed problems with stop
point after a suite reload: do not reset an existing stop point (this is
dangerous, but it could be done before, and the stop point in the GUI status
bar would still refer to the original)

[#2562](https://github.com/cylc/cylc-flow/pull/2562) - improved advice on how to
generate an initial user config file (`global.rc`)

-------------------------------------------------------------------------------
## __cylc-7.5.0 (2017-08-29)__

### Enhancements

[#2387](https://github.com/cylc/cylc-flow/pull/2387),
[#2330](https://github.com/cylc/cylc-flow/pull/2330): New suite.rc `[meta]` sections
for suite and task metadata. These hold the existing `title`, `description`,
and `URL` items, plus arbitrary user-defined items. Metadata items can be passed
to event handlers (e.g. a site-specific task "priority" or "importance" rating
could inform an event-handler's decision on whether or not to escalate task
failures).

[#2298](https://github.com/cylc/cylc-flow/pull/2298),
[#2401](https://github.com/cylc/cylc-flow/pull/2401): New shell function
`cylc__job_abort <message>` to abort task job scripts with a custom message
that can be passed to task failed event handlers.

[#2204](https://github.com/cylc/cylc-flow/pull/2204): Remove auto-fallback to HTTP
communications, if HTTPS is not available.  Now HTTP is only used if explicitly
configured.

[#2332](https://github.com/cylc/cylc-flow/pull/2332),
[#2325](https://github.com/cylc/cylc-flow/pull/2325),
[#2321](https://github.com/cylc/cylc-flow/pull/2321),
[#2312](https://github.com/cylc/cylc-flow/pull/2312): Validation efficiency
improvements.

[#2291](https://github.com/cylc/cylc-flow/pull/2291),
[#2303](https://github.com/cylc/cylc-flow/pull/2303),
[#2322](https://github.com/cylc/cylc-flow/pull/2322): Runtime efficiency
improvements.

[#2286](https://github.com/cylc/cylc-flow/pull/2286): New command `cylc
report-timings` to generate reports of task runtime statistics.

[#2304](https://github.com/cylc/cylc-flow/pull/2304): New event handlers for general
CRITICAL events.

[#2244](https://github.com/cylc/cylc-flow/pull/2244),
[#2258](https://github.com/cylc/cylc-flow/pull/2258): Advanced syntax for excluding
multiple points from cycling sequences.

[#2407](https://github.com/cylc/cylc-flow/pull/2407): Documented exactly how Cylc
uses ssh, scp, and rsync to interact with remote job hosts.

[#2346](https://github.com/cylc/cylc-flow/pull/2346),
[#2386](https://github.com/cylc/cylc-flow/pull/2386): `cylc graph` now plots
implicit dependences as grayed-out ghost nodes.

[#2343](https://github.com/cylc/cylc-flow/pull/2343): Improved the "Running
Suites" section of the User Guide, including documentation of suite remote
control.

[#2344](https://github.com/cylc/cylc-flow/pull/2344): Attempt to access suite
service files via the filesystem first, before ssh, for other accounts on the
suite host.

[#2360](https://github.com/cylc/cylc-flow/pull/2360): Better validation of suite
parameter configuration.

[#2314](https://github.com/cylc/cylc-flow/pull/2314): In debug mode, send bash job
script xtrace output (from `set -x`) to a separate log file.

### Fixes

[#2409](https://github.com/cylc/cylc-flow/pull/2409): Fixed the `cylc spawn` command
(it was killing tasks, since cylc-7).

[#2378](https://github.com/cylc/cylc-flow/pull/2378): Fixed use of negative offsets
by the `cylc suite-state` command.

[#2364](https://github.com/cylc/cylc-flow/pull/2364): Correctly load completed custom
task outputs on restart.

[#2350](https://github.com/cylc/cylc-flow/pull/2350): Handle bad event handler
command line templates gracefully.

[#2308](https://github.com/cylc/cylc-flow/pull/2308): The parameterized task
environment variable `$CYLC_TASK_PARAM_<param>` is now guaranteed to be defined
before any use of it in the user-defined task environment section.

[#2296](https://github.com/cylc/cylc-flow/pull/2296): Prevent suites stalling after
a restart that closely follows a warm-start (now the restart, like the warm
start, ignores dependence on tasks from before the warm start point).

[#2295](https://github.com/cylc/cylc-flow/pull/2295): Fixed `cylc cat-log` "open in
editor" functionality for remote job logs.

[#2412](https://github.com/cylc/cylc-flow/pull/2412): Fixed duplication of log
messages to the old log after restart.

-------------------------------------------------------------------------------

## __cylc-7.4.0 (2017-05-16)__

Enhancements and fixes.

### Highlighted Changes

[#2260](https://github.com/cylc/cylc-flow/pull/2260): Open job logs in your text
editor, from CLI (`cylc cat-log`) or GUI.

[#2259](https://github.com/cylc/cylc-flow/pull/2259): `cylc gscan` - various
improvements: right-click menu is now for suite operations only; other items
moved to a main menubar and toolbar (which can be hidden to retain gscan's
popular minimalist look); added all suite stop options (was just the default
clean stop); task-state colour-key popup updates in-place if theme changed; new
collapse/expand-all toobar buttons.

[#2275](https://github.com/cylc/cylc-flow/pull/2275): Pass suite and task URLs to
event handlers.

[#2272](https://github.com/cylc/cylc-flow/pull/2272): Efficiency - reduce memory
footprint.

[#2157](https://github.com/cylc/cylc-flow/pull/2157):
  * internal efficiency improvements
  * allow reset of individual message outputs
  * "cylc submit" can now submit families

[#2244](https://github.com/cylc/cylc-flow/pull/2244): Graph cycling configuration:
multiple exclusion points.

[#2240](https://github.com/cylc/cylc-flow/pull/2240): Stepped integer parameters.

### Fixes

[#2269](https://github.com/cylc/cylc-flow/pull/2269): Fix auto suite-polling tasks
(i.e. inter-suite dependence graph syntax) - Broken in 7.3.0.

[#2282](https://github.com/cylc/cylc-flow/pull/2282): Fix global config processing
of boolean settings - users could not override a site True setting to False.

[#2279](https://github.com/cylc/cylc-flow/pull/2279): Bundle Jinja2 2.9.6. (up from
2.8) - fixes a known issue with Jinja2 "import with context".

[#2255](https://github.com/cylc/cylc-flow/pull/2255): Fix handling of suite script
items that contain nothing but comments.

[#2247](https://github.com/cylc/cylc-flow/pull/2247): Allow `cylc graph --help`
in the absence of an X environment.

### Other Changes

[#2270](https://github.com/cylc/cylc-flow/pull/2270): Detect and fail null tasks in
graph.

[#2257](https://github.com/cylc/cylc-flow/pull/2257): `cylc gscan` - graceful exit
via Ctrl-C.

[#2252](https://github.com/cylc/cylc-flow/pull/2252): `ssh`: add `-Y` (X Forwarding)
only if necessary.

[#2245](https://github.com/cylc/cylc-flow/pull/2245): SSL certficate: add serial
number (issue number). This allows curl, browsers, etc. to connect to
suite daemons.

[#2265](https://github.com/cylc/cylc-flow/pull/2265): `cylc gpanel` - restored
sorting of items by suite name.

[#2250](https://github.com/cylc/cylc-flow/issues/2250): Updated installation docs
for HTTPS-related requirements.

-------------------------------------------------------------------------------
## __cylc-7.3.0 (2017-04-10)__

New Suite Design Guide, plus other enhancements and fixes.

### Highlighted Changes

[#2211](https://github.com/cylc/cylc-flow/pull/2211): New comprehensive Suite Design
Guide document to replace the outdated Suite Design section in the User Guide.

[#2232](https://github.com/cylc/cylc-flow/pull/2232): `cylc gscan` GUI: stop, hold,
and release suites or groups of suites.

[#2220](https://github.com/cylc/cylc-flow/pull/2220): dummy and simulation mode improvements:
 * new `dummy-local` mode runs dummy tasks as local background jobs (allows
   dummy running other-site suites).
 * proportional run length, if tasks configure an `execution time limit`
 * single common `[simulation]` configuration section for dummy, dummy-local, and
   simulation modes.
 * dummy or simulated tasks can be made to fail at specific cycle points, and
   for first-try only, or all tries.
 * custom message outputs now work in simulation mode as well as the dummy modes.

[#2218](https://github.com/cylc/cylc-flow/pull/2218): fix error trapping in job
scripts (degraded since job file refactoring in 7.1.1)

[#2215](https://github.com/cylc/cylc-flow/pull/2215): SGE batch system support -
fixed formatting of directives with a space in the name.

### Other Notable Changes

[#2233](https://github.com/cylc/cylc-flow/pull/2233): Upgraded the built-in example
suites to cylc-7 syntax.

[#2221](https://github.com/cylc/cylc-flow/pull/2221): `cylc gui` GUI dot view - maintain
user selection during update.

[#2217](https://github.com/cylc/cylc-flow/pull/2217): `cylc gscan` GUI - fix
tracebacks emitted during suite initialization.

[#2219](https://github.com/cylc/cylc-flow/pull/2219): add `user@host` option to
`cylc monitor` an `cylc gui`. Allows suite selection at startup using `cylc
scan` output.

[#2222](https://github.com/cylc/cylc-flow/pull/2222): `cylc gui` GUI graph view -
fixed right-click "view prerequisites" sub-menu.

[#2213](https://github.com/cylc/cylc-flow/pull/2213): Record family inheritance
structure in the run database.

-------------------------------------------------------------------------------
## __cylc-7.2.1 (2017-03-23)__

Minor enhancements and fixes.

### Highlighted Changes

[#2209](https://github.com/cylc/cylc-flow/pull/2209): Fixed the `cylc gui` graph
view, broken at cylc-7.2.0.

[#2193](https://github.com/cylc/cylc-flow/pull/2193): Restored `cylc gscan`
suite-stopped status checkerboard icons, lost at cylc-7.1.1.


[#2208](https://github.com/cylc/cylc-flow/pull/2208): Use suite host name instead
of suite name in the SSL certificate "common name".

[#2206](https://github.com/cylc/cylc-flow/pull/2206): Updated User Guide
installation section.

### Other Notable Changes

[#2191](https://github.com/cylc/cylc-flow/pull/2191): Clearer task prerequisites
print-out.

[#2197](https://github.com/cylc/cylc-flow/pull/2197): Removed the bundled external
OrderedDict package.

[#2194](https://github.com/cylc/cylc-flow/pull/2194): `cylc gscan` - better handling
of suites that are still initializing.

-------------------------------------------------------------------------------
## __cylc-7.2.0 (2017-03-06)__

Minor enhancements and fixes (note mid-level version number bumped up to
reflect significant changes included in 7.1.1 - esp. job file refactoring).

### Highlighted Changes

[#2189](https://github.com/cylc/cylc-flow/pull/2184): New `assert` and
`raise` functions for handling Jinja2 errors in suites.

### Other Changes

[#2186](https://github.com/cylc/cylc-flow/pull/2186): Use lowercase local shell
variable names in new job script shell functions introduced in 7.1.1, to avoid
overriding shell built-ins such as `$HOSTNAME`.

[#2187](https://github.com/cylc/cylc-flow/pull/2187): Fixed a bug causing restart
failure in the presence of an active broadcast of a submission timeout value.

[#2183](https://github.com/cylc/cylc-flow/pull/2183): Use site-configured suite host
self-identification, if present, as hostname in the SSL certificate.

[#2182](https://github.com/cylc/cylc-flow/pull/2182): Fixed failed User Guide build
in 7.1.1.

-------------------------------------------------------------------------------
## __cylc-7.1.1 (2017-02-27)__

Minor enhancements and fixes (plus a significant change: task job file refactoring).

### Highlighted Changes

[#2141](https://github.com/cylc/cylc-flow/pull/2141): Tidier task job files:
hide error trap and messaging code, etc., in external shell functions.

[#2134](https://github.com/cylc/cylc-flow/pull/2134): Suite-state polling (e.g. for
inter-suite triggering) now automatically detects and uses the remote suite
cycle point format.

[#2128](https://github.com/cylc/cylc-flow/pull/2128): Suite-state polling
(e.g. for inter-suite triggering) now works with custom task messages.

[#2172](https://github.com/cylc/cylc-flow/pull/2172): Added a built-in Jinja2 filter
for formatting ISO8601 date-time strings.

[#2164](https://github.com/cylc/cylc-flow/pull/2164): Fixed support for Jinja2 in
site/user config files, broken at 6.11.0.

[#2153](https://github.com/cylc/cylc-flow/pull/2153): `cylc gui` - use task
`execution time limit` as the default mean elapsed time, to compute a progress
bar for the first instance of a cycling task.

[#2154](https://github.com/cylc/cylc-flow/pull/2154): `cylc gui` graph view - fixed
right-click sub-menu activation, broken at 7.1.0.

[#2158](https://github.com/cylc/cylc-flow/pull/2158): `cylc gui` graph view: fix
right-click family ungroup, broken since 7.0.0.

### Other Changes

[#2142](https://github.com/cylc/cylc-flow/pull/2142): New "select all" and "select
none" buttons in the `cylc gui` task filter dialog.

[#2163](https://github.com/cylc/cylc-flow/pull/2163): (Development) New automated
profiling test framework for comparing performance between Cylc versions.

[#2160](https://github.com/cylc/cylc-flow/pull/2160): Better suite stall detection
in the presence of clock-triggered tasks.

[#2156](https://github.com/cylc/cylc-flow/pull/2156): Fix potential division-by-zero
error in `cylc gscan`.

[#2149](https://github.com/cylc/cylc-flow/pull/2149): Fix handling of cycle point
offsets in weeks (e.g. "P1W").

[#2146](https://github.com/cylc/cylc-flow/pull/2146): Documented how to set multiple
`-l VALUE` directives in jobs submitted to PBS.

[#2129](https://github.com/cylc/cylc-flow/pull/2129): Allow initial cycle point to be
specified on the command line for all relevant commands, if not specified in the
suite definition.

[#2139](https://github.com/cylc/cylc-flow/pull/2139): Fixed error in use of
`execution time limit` in jobs submitted to Platform LSF.

[#2176](https://github.com/cylc/cylc-flow/pull/2176): `cylc gui` graph view - fixed
a bug that could cause a blank graph view window, since 7.0.0.

[#2161](https://github.com/cylc/cylc-flow/pull/2161): `gcylc gui`- disallow
insertion at cycle points that are not valid for the task (unless overridden
with `--no-check`).

-------------------------------------------------------------------------------
## __cylc-7.1.0 (2017-01-26)__

Minor enhancements and fixes.

### Highlighted Changes

[#2021](https://github.com/cylc/cylc-flow/pull/2021): New command `cylc checkpoint`
to create a named suite state checkpoint that you can restart from.

[#2124](https://github.com/cylc/cylc-flow/pull/2124): open another GUI window (to
view another suite) via the gcylc File menu.

[#2100](https://github.com/cylc/cylc-flow/pull/2100): group multiple task event
notifications into a single email over a 5 minute interval (configurable).

[#2112](https://github.com/cylc/cylc-flow/pull/2112): broadcast settings can now be
loaded (or cancelled) from a file as well as the command line.

[#2096](https://github.com/cylc/cylc-flow/pull/2096): the `cylc gscan` GUI can now
display summary states for suites owned by others.

### Other Changes

[#2126](https://github.com/cylc/cylc-flow/pull/2126): fixed occasional
misidentification of suite stall when only succeeded tasks exist just prior to
shutdown.

[#2127](https://github.com/cylc/cylc-flow/pull/2127): fixed the `cylc diff` command
(broken at 7.0.0)

[#2119](https://github.com/cylc/cylc-flow/pull/2119): fixed remote job kill after a
suite definition reload, for task proxies that exist at the time of the reload.

[#2025](https://github.com/cylc/cylc-flow/pull/2025): GUI right-click menu items can
now be selected with either mouse button 1 or 3.

[#2117](https://github.com/cylc/cylc-flow/pull/2117): improved logic for adding
`lib/cylc` to Python `sys.path` (there was one reported instance of the
system-level `cherrpy` being imported instead of the Cylc-bundled one, in
cylc-7.0.0).

[#2114](https://github.com/cylc/cylc-flow/pull/2114): documented syntax-driven line
continuation in suite graph configuration.

[#2116](https://github.com/cylc/cylc-flow/pull/2116): corrected a rare edge-case
side-effect of manual task-state reset.

[#2107](https://github.com/cylc/cylc-flow/pull/2107): `cylc insert` - disallow
insertion at cycle points that are not valid for the task (unless overridden
with `--no-check`).

[#2106](https://github.com/cylc/cylc-flow/pull/2106): fixed `cylc get-config
--python` output formatting, broken since cylc-6.6.0.

[#2097](https://github.com/cylc/cylc-flow/pull/2097): fixed a problem with task host
and owner task proxies reloaded at suite restart (could cause job poll and
kill to fail in some cases, for tasks in this category).

[#2095](https://github.com/cylc/cylc-flow/pull/2095): fixed validation of mixed
deprecated and new suite.rc syntax.

## __cylc-7.0.0 (2016-12-21)__

**cylc-7 client/server communications is not backward compatible with cylc-6.**

Note that cylc-7 bug fixes were back-ported to a series of 6.11.x releases,
for those who have not transitioned to cylc-7 yet.

### Highlighted Changes

[#1923](https://github.com/cylc/cylc-flow/pull/1923): **A new HTTPS communications
layer, replaces Pyro-3 Object RPC for all client-server communications.**
Suite daemons are now web servers!

[#2063](https://github.com/cylc/cylc-flow/pull/2063): **Removed deprecated cylc-5
syntax and features.**

[#2044](https://github.com/cylc/cylc-flow/pull/2044): Suite start-up now aborts with
a sensible message on suite configuration errors (previously this happened post
daemonization so the user had to check suite logs to see the error).

[#2067](https://github.com/cylc/cylc-flow/pull/2067): Consolidated suite service
files (passphrase, SSL files, contact file, etc.) under `.service/` in the
suite run directory; the suite registration database and port files under
`$HOME/.cylc/` are no longer used; suites can now be grouped in sub-directory
trees under the top level run directory.

[#2033](https://github.com/cylc/cylc-flow/pull/2033): Allow restart from suite state
checkpoints other than the latest (checkpoints are also recorded automatically
before and after restarts, and on reload).

[#2024](https://github.com/cylc/cylc-flow/pull/2024): `cylc gscan` now supports
collapsible suite groups via a top level suite config `group` item.
Right-click *View Column* "Group".

[#2074](https://github.com/cylc/cylc-flow/pull/2074): Task retry states and timers,
and poll timers, now persist across suite restarts. Waiting tasks are not
put in the held state before shutdown. Held tasks are not automatically
released on restart.

[#2004](https://github.com/cylc/cylc-flow/pull/2004): Task event handlers are
now continued on restart.

### Other Changes

[#2042](https://github.com/cylc/cylc-flow/pull/2042): Documented `[scheduling]spawn
to max active cycle points` (new in 6.11.0), which lets successive instances of
the same task run out of order if dependencies allow.

[#2092](https://github.com/cylc/cylc-flow/pull/2092): New command `cylc
get-suite-contact` to print suite contact information (host, port, PID, etc.)

[#2089](https://github.com/cylc/cylc-flow/pull/2089): Improved documentation on
cycling workflows and use of parameterized tasks as a proxy for cycling.

[#2021](https://github.com/cylc/cylc-flow/pull/2021): `cylc gui`: removed the
"connection failed" warning dialog that popped up on suite shutdown. This
should be obvious by the reconnection countdown timer in the info bar.

[#2023](https://github.com/cylc/cylc-flow/pull/2023): New custom event email footer
via global or suite config.

[#2013](https://github.com/cylc/cylc-flow/pull/2013): Fixed "remove task after
spawning" which since 6.9.0 would not force a waiting task to spawn its
successor.

[#2071](https://github.com/cylc/cylc-flow/pull/2071): Fix quote stripping on
`initial cycle point = "now"`.

[#2070](https://github.com/cylc/cylc-flow/pull/2070): Fix dummy mode support for
custom task outputs: they were incorrectly propagated to other tasks.

[#2065](https://github.com/cylc/cylc-flow/pull/2065): `cylc gscan` now supports
suite name filtering via a `--name` command line option.

[#2060](https://github.com/cylc/cylc-flow/pull/2060): 5-second timeout if hanging
connections are encountered during port scanning.

[#2055](https://github.com/cylc/cylc-flow/pull/2055): Task elapsed times now persist
over restarts.

[#2046](https://github.com/cylc/cylc-flow/pull/2046): Multi-task interface for `cylc
show`. Fixed *View Prerequisites* for tasks in the runahead pool.

[#2049](https://github.com/cylc/cylc-flow/pull/2049): Per-host job submission and
execution polling intervals via global/user config files.

[#2051](https://github.com/cylc/cylc-flow/pull/2051): Bundle Jinja2 2.8 with Cylc -
one less external software dependency.

[#2088](https://github.com/cylc/cylc-flow/pull/2088): Support dependence on absolute
cycle points in cycling graphs.

## __cylc-6.11.4 (2017-01-26)__

More bug fixes backported from early Cylc-7 releases.

[#2120](https://github.com/cylc/cylc-flow/pull/2120): fixed remote job kill after a
+suite definition reload, for task proxies that exist at the time of the reload.

[#2111](https://github.com/cylc/cylc-flow/pull/2111): fixed member-expansion of
complex `(FAMILY:fail-any & FAMILYI:finish-all)` graph triggers.

[#2102](https://github.com/cylc/cylc-flow/pull/2102): fixed validation of mixed
deprecated and new suite.rc syntax.

[#2098](https://github.com/cylc/cylc-flow/pull/2098): fixed a problem with task host
and owner task proxies reloaded at suite restart (could cause job poll and
kill to fail in some cases, for tasks in this category).


## __cylc-6.11.3 (2016-12-21)__

One minor bug fix on top of 6.11.2.

[#2091](https://github.com/cylc/cylc-flow/pull/2091): Since 6.11.0 use of cylc-5
special "cold start tasks" caused downstream tasks to become immortal. This
fixes the problem, but note that you should no longer be using this deprecated
feature (which will be removed from cylc-7).


## __cylc-6.11.2 (2016-10-19)__

Some minor enhancements and fixes.

### Highlighted Changes

[#2034](https://github.com/cylc/cylc-flow/pull/2034): Allow restart from checkpoints.
These are currently created before and after reloads, and on restart. (Note that
since 6.11.0 suite state dump files no longer exist).

[#2047](https://github.com/cylc/cylc-flow/pull/2047): Documented the new
"[scheduling]spawn to max active cycle points" suite configuration item,
which allows successive instances of the same task to run out of order if the
opportunity arises.

[#2048](https://github.com/cylc/cylc-flow/pull/2048): Allow "view prerequisites" for
tasks in the 'runahead' state.

[#2025](https://github.com/cylc/cylc-flow/pull/2025): Provide a configurable event
mail footer (suite or site/user configuration).

[#2032](https://github.com/cylc/cylc-flow/pull/2032): `cylc gui` -
removed the annoying warning dialog for connection failed. Take note of the
connection countdown in the status bar instead.

### Other Changes

[#2016](https://github.com/cylc/cylc-flow/pull/2016): Fixed a Python traceback
occasionally generated by the gcylc GUI log view window.

[#2018](https://github.com/cylc/cylc-flow/pull/2018): Restored the incremental
printing of dots to stdout from the `cylc suite-state` polling
command (lost at 6.11.1).

[#2014](https://github.com/cylc/cylc-flow/pull/2014): Fixed "remove after spawning".
Since 6.9.0 this would not force-spawn the successor of a waiting task.

[#2031](https://github.com/cylc/cylc-flow/pull/2031): `cylc gscan` -
fixed occasional jumping status icons introduced in 6.11.1.

[#2040](https://github.com/cylc/cylc-flow/pull/2040): Corrected documentation for
the `cylc cat-log` command (it was using the alias `cylc
log`).


## __cylc-6.11.1 (2016-09-22)__

Three minor bug fixes on top of 6.11.0:

[#2002](https://github.com/cylc/cylc-flow/pull/2002): fix a bug in the graph string
parser - if a task appears both with and without a cycle point offset in the
same conditional trigger expression (unlikely, but possible!)

[#2007](https://github.com/cylc/cylc-flow/pull/2007): fix handling of OS Error if
the user run into the limit for number of forked processes.

[#2008](https://github.com/cylc/cylc-flow/pull/2008): fix occasional traceback from
`cylc gsan`.



## __cylc-6.11.0 (2016-09-13)__

### Highlighted Changes

[#1953](https://github.com/cylc/cylc-flow/pull/1953): Parameterized tasks: generate
tasks automatically without using messy Jinja2 loops.

[#1929](https://github.com/cylc/cylc-flow/pull/1929): Under `[runtime]`:
 * New task `[[[job]]]` sub-sections unify the various batch system, job
   execution, and job polling settings (older settings deprecated).
 * A new `[[[job]]] execution time limit` setting allows cylc to:
    * automatically generate batch system time limit directives;
    * run background or at jobs with the `timeout` command;
    * poll job with configurable delays (default 1, 3, 10 minutes) after
      reaching the time limit.
 * Moved the content of the old `[event hooks]` section to a unified `[events]`
   section (older settings deprecated).

[#1884](https://github.com/cylc/cylc-flow/pull/1884): `cylc gscan` displays a new
warning icon with a tool-tip summary of recent task failures.

[#1877](https://github.com/cylc/cylc-flow/pull/1877): The `gcylc` status bar now
shows a countdown to the next suite connection attempt, and resets the
connection timer schedule if the user changes view settings.

[#1966](https://github.com/cylc/cylc-flow/pull/1966): Optionally spawn waiting tasks
out to "max active cycle points" instead of one cycle point ahead. This means
successive instances of the same task can run out of order (dependencies
allowing).  Use with caution on large suites with a lot of runahead.

[#1940](https://github.com/cylc/cylc-flow/pull/1940): Bash tab completion for cylc
commands.

### Other Changes

[#1585](https://github.com/cylc/cylc-flow/pull/1585): If a suite stalls, report any
unsatisified task prerequisites that cannot be met.

[#1944](https://github.com/cylc/cylc-flow/pull/1944): `cylc get-config` now returns
a valid suite definition.

[#1875](https://github.com/cylc/cylc-flow/pull/1875): Enabled multiple selection in
the gcylc text tree view.

[#1900](https://github.com/cylc/cylc-flow/pull/1900): Automatically continue graph
string lines that end in (or start with) a dependency arrow.

[#1862](https://github.com/cylc/cylc-flow/pull/1862): New notation for initial and
final cycle point in graph cycling section headings.  E.g. `[[[R1/^+PT1H]]]`
means "run once, one hour after the initial cycle point"; `[[[R1/$-PT1H]]]`
means "run once, one hour before the final cycle point".

[#1928](https://github.com/cylc/cylc-flow/pull/1928): New notation for excluding a
cycle point from a recurrence expression, e.g. `[[[T00!^]]]` means
"daily at T00 after but not including the initial cycle point".

[#1958](https://github.com/cylc/cylc-flow/pull/1958): Suite daemon logging upgrade:
improved log file formatting; the log, out, and err files are now rolled over
together as soon as any one reaches the size limit.

[#1827](https://github.com/cylc/cylc-flow/pull/1827): Suite state dump files no
longer exist - the suite run DB now records all restart information.

[#1912](https://github.com/cylc/cylc-flow/pull/1912): Fixed coloured `cylc scan -c`
output (broken at 6.10.1).

[#1921](https://github.com/cylc/cylc-flow/pull/1921): Don't ignore dependencies
among tasks back-inserted prior to a warm-start cycle point.

[#1910](https://github.com/cylc/cylc-flow/pull/1910): Task job scripts now use `set
-o pipefail` to ensure that failure of any part of a shell pipeline causes a
job failure.

[#1886](https://github.com/cylc/cylc-flow/pull/1886): When a job is submitted for
the first time, any job logs with higher submit numbers will be removed (
these must have been generated by a previous suite run).

[#1946](https://github.com/cylc/cylc-flow/pull/1946): Removed annoying warnings
that "self-suicide is not recommended".

[#1889](https://github.com/cylc/cylc-flow/pull/1889): Record any unhandled task
messages (e.g. general progress messages) in the suite DB.

[#1899](https://github.com/cylc/cylc-flow/pull/1899): Custom task output messages
(for message triggers) are now automatically faked in dummy mode.

-------------------------------------------------------------------------------

## __cylc-6.10.2 (2016-06-02)__

### Highlighted Changes

[#1848](https://github.com/cylc/cylc-flow/pull/1848): Automatic stalled-suite
detection, a "stalled" event hook, and an option to abort (shutdown) if stalled.

[#1850](https://github.com/cylc/cylc-flow/pull/1850): Much reduced CPU loading in
cycling suites that have progressed far beyond their initial cycle point (cache
recent points to avoid continually iterating from the start).

[#1836](https://github.com/cylc/cylc-flow/pull/1836): New `gscan.rc` file to
configure the initial state of `cylc gpanel` and `cylc gscan` (e.g. which
columns to display).

[#1849](https://github.com/cylc/cylc-flow/pull/1849): New configuration options for
the `gcylc` GUI, e.g. to set the initial window size.


### Other Changes

[#1863](https://github.com/cylc/cylc-flow/pull/1863): Report tasks added or removed
by a suite reload.

[#1844](https://github.com/cylc/cylc-flow/pull/1844): Allow client commands from
another suite's task (these would previously load the passphrase for the parent
suite rather than the target suite).

[#1866](https://github.com/cylc/cylc-flow/pull/1866): Allow explicitly unset
intervals in cylc config files, e.g. `execution timeout = # (nothing)`.

[#1863](https://github.com/cylc/cylc-flow/pull/1863): Fixed a recent bug (since in
6.10.0) causing shutdown on reload of a suite after removing a task and its
runtime definition.

[#1864](https://github.com/cylc/cylc-flow/pull/): Stronger checks to prevent users
starting a second instance of a suite that is already running.

[#1869](https://github.com/cylc/cylc-flow/pull/1869): Fixed day-of-week cycling.

[#1858](https://github.com/cylc/cylc-flow/pull/1858): Fixed a recent bug (since
6.10.1) that could prevent a task at suite start-up from submitting even though
its prerequisites were satisfied.

[#1855](https://github.com/cylc/cylc-flow/pull/1855): Allow inserted tasks to be
released to the `waiting` immediately, even if the suite is currently quiet.

[#1854](https://github.com/cylc/cylc-flow/pull/): Restore wildcards to allow
insertion of multiple tasks at once (inadvertently disallowed at 6.10.0).

[#1853](https://github.com/cylc/cylc-flow/pull/1853): Fixed a recent bug (since
6.10.1): reset task outputs to incomplete on manually retriggering or resetting
to a pre-run state.

-------------------------------------------------------------------------------

## __cylc-6.10.1 (2016-05-17)__

### Highlighted Changes

[#1839](https://github.com/cylc/cylc-flow/pull/1839): `gcylc` - fix for occasional
locked-up blank GUI window at start-up (since 6.8.0, Jan 2016).

[#1841](https://github.com/cylc/cylc-flow/pull/1841): `gcylc` tree view - fix for
excessive CPU load when displaying large suites (since 6.10.0).

[#1838](https://github.com/cylc/cylc-flow/pull/1838): Fix for the suite timeout
event timer not resetting on task activity (since 6.10.0).

### Other Changes

[#1835](https://github.com/cylc/cylc-flow/pull/1835): Suite reload - reload all
tasks at once (previously, current active tasks were reloaded only when they
finished, which could result in reloads appearing to take a long time).

[#1833](https://github.com/cylc/cylc-flow/pull/1833): `gcylc` - initial task state
filtering configurable via the  `gcylc.rc` config file.

[#1826](https://github.com/cylc/cylc-flow/pull/1826): Prevent tasks becoming immune
to change by suite reload after being orphaned by one reload (i.e. removed from
the suite) then re-inserted after another.

[#1804](https://github.com/cylc/cylc-flow/pull/1804): PBS job name length - truncate
to 15 characters by default, but can now be configured in `global.rc` for PBS
13+, which supports longer names.

-------------------------------------------------------------------------------

## __cylc-6.10.0 (2016-05-04)__

### Highlighted Changes

[#1769](https://github.com/cylc/cylc-flow/pull/1769),
[#1809](https://github.com/cylc/cylc-flow/pull/1809),
[#1810](https://github.com/cylc/cylc-flow/pull/1810),
[#1811](https://github.com/cylc/cylc-flow/pull/1811),
[#1812](https://github.com/cylc/cylc-flow/pull/1812),
[#1813](https://github.com/cylc/cylc-flow/pull/1813),
[#1819](https://github.com/cylc/cylc-flow/pull/1819): Suite daemon efficiency
and memory footprint - significant improvements!

[#1777](https://github.com/cylc/cylc-flow/pull/1777): Faster validation of
suites with large inter-dependent families.  See also
[#1791](https://github.com/cylc/cylc-flow/pull/1791).

[#1743](https://github.com/cylc/cylc-flow/pull/1743): Improved event handling:
flexible handlers, built-in email handlers, execute event handlers
asynchronously, general suite event handlers.

[#1729](https://github.com/cylc/cylc-flow/pull/1729): `gcylc` - The *File -> Open*
dialog can now connect to suites running on other scanned hosts.

[#1821](https://github.com/cylc/cylc-flow/pull/1821): Right-click on a cycle-point
in the `gcylc` text tree view to operate on all tasks at that cycle point.

### Other Changes

[#1714](https://github.com/cylc/cylc-flow/pull/1714): Further improvements to Jinja2
error reporting.

[#1755](https://github.com/cylc/cylc-flow/pull/1755): Pyro-3.16 is now packaged with
with cylc and has been modified to reduce the overhead of repeated calls to
`socket.gethost*`. We will eventually replace it with a new client/server
communications layer.

[#1807](https://github.com/cylc/cylc-flow/pull/1807): Dropped support for
_detaching_ (or _manual completion_) tasks.

[#1805](https://github.com/cylc/cylc-flow/pull/1805): `gcylc` - corrected the suite
hold/release button state during  active suite reloads.

[#1802](https://github.com/cylc/cylc-flow/pull/1802): Do not unregister running
suites or assume that the argument of `cylc unregister` is a pattern.

[#1800](https://github.com/cylc/cylc-flow/pull/1800): Print a sensible error message
for a suite graph section with a zero-width cycling interval.

[#1791](https://github.com/cylc/cylc-flow/pull/1791): Documented how to write suites
with efficient inter-family triggering.

[#1789](https://github.com/cylc/cylc-flow/pull/1789): Fixed a bug causing high CPU
load in large suites with `queued` tasks present.

[#1788](https://github.com/cylc/cylc-flow/pull/1788): Fixed a bug that could
occasionally result in missing entries in suite run databases.

[#1784](https://github.com/cylc/cylc-flow/pull/1784): Corrected and improved the
advice printed at start-up on how to see if a suite is still running.

[#1781](https://github.com/cylc/cylc-flow/pull/1781): Fixed a bug that could disable
the right-click menu for some tasks after enabling a filter.

[#1768](https://github.com/cylc/cylc-flow/pull/1768): Client commands like `cylc
broadcast` can now be invoked by tasks on remote hosts that do not share a
filesystem with the suite host.

[#1763](https://github.com/cylc/cylc-flow/pull/1763): Remote tasks now load
the right suite passphrase even if a locally registered suite has
the same name.

[#1762](https://github.com/cylc/cylc-flow/pull/1762): Fixed polling of jobs
submitted to loadleveler (broken since 6.8.1).

[#1816](https://github.com/cylc/cylc-flow/pull/1819),
[#1779](https://github.com/cylc/cylc-flow/pull/1779): Allow task names that contain
family names after a hyphen.

-------------------------------------------------------------------------------

#### For changes prior to cylc-6.10.0 see doc/changes.html in the cylc source tree.
