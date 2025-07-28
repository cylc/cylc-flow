# Changelog

List of notable changes, for a complete list of changes see the
[closed milestones](https://github.com/cylc/cylc-flow/milestones?state=closed)
for each release.

<!--
NOTE: Do not add entries here, use towncrier fragments instead:
$ towncrier create <PR-number>.<break|feat|fix>.md --content "Short description"
-->

<!-- towncrier release notes start -->

## __cylc-8.5.0 (Released 2025-07-24)__

### 🚀 Enhancements

[#6117](https://github.com/cylc/cylc-flow/pull/6117) - Create `workflow/share/cycle/<cycle>` and make it available to jobs as `$CYLC_TASK_SHARE_CYCLE_DIR`.

[#6395](https://github.com/cylc/cylc-flow/pull/6395) - `cylc trigger` now respects the dependencies between tasks allowing it to be used to (re)-run a subgraph of tasks.

[#6478](https://github.com/cylc/cylc-flow/pull/6478) - Major version upgrade for graphene/graphql-core dependencies.

[#6509](https://github.com/cylc/cylc-flow/pull/6509) - Added --global flag to 'cylc reload' which also reloads the Cylc global config.

[#6554](https://github.com/cylc/cylc-flow/pull/6554) - `cylc show` now displays when a task has been set to skip mode

[#6561](https://github.com/cylc/cylc-flow/pull/6561) - Tui now displays task states and flow numbers in context menus. Tasks in flow=None will be displayed in gray.

[#6570](https://github.com/cylc/cylc-flow/pull/6570) - Using `cylc set` without specifying `--out` on a task where success is optional now sets success pathway outputs instead of doing nothing.

[#6611](https://github.com/cylc/cylc-flow/pull/6611) - Tui: Add ability to open log files in external tools. Configure your `$EDITOR`, `$GEDITOR` or `$PAGER` options to choose which tool is used.

[#6695](https://github.com/cylc/cylc-flow/pull/6695) - Extended the "set" command to manually satisfy dependence on xtriggers.

### 🔧 Fixes

[#6549](https://github.com/cylc/cylc-flow/pull/6549) - Removed cylc.vim - you should use https://github.com/cylc/cylc.vim instead.

[#6574](https://github.com/cylc/cylc-flow/pull/6574) - Broadcast: Report any settings that are not compatible with the scheduler Cylc version.

[#6625](https://github.com/cylc/cylc-flow/pull/6625) - Efficiency improvement: avoid storing duplicate information on graph triggers.

[#6753](https://github.com/cylc/cylc-flow/pull/6753) - Fixes an issue where duplicate xtrigger labels were missing from `cylc show`.

[#6838](https://github.com/cylc/cylc-flow/pull/6838) - Workflow and task `handler events` and `mail events` names are now validated. Outdated Cylc 7 workflow event names are automatically upgraded.

[#6852](https://github.com/cylc/cylc-flow/pull/6852) - Removed predicted (and potentially incorrect) flow numbers from n>0 window tasks.

[#6856](https://github.com/cylc/cylc-flow/pull/6856) - Fix a niche bug where outputs of a task could be wiped from the database if it was subsequently suicide triggered (e.g, if a custom output was manually set before the suicide trigger occurred).

## __cylc-8.4.4 (Released 2025-07-18)__

### 🔧 Fixes

[#6798](https://github.com/cylc/cylc-flow/pull/6798) - Prevent unintended submission retries that could result from platform connection issues in certain circumstances.

[#6828](https://github.com/cylc/cylc-flow/pull/6828) - Simulation mode will no longer erroneously complain about unsatisfied custom outputs.

## __cylc-8.4.3 (Released 2025-06-17)__

### 🚀 Enhancements

[#6730](https://github.com/cylc/cylc-flow/pull/6730) - Add SQLite detailed error codes to error logs

### 🔧 Fixes

[#6602](https://github.com/cylc/cylc-flow/pull/6602) - Fix a bug where suicide triggers could prevent initial cycle point tasks spawning.

[#6710](https://github.com/cylc/cylc-flow/pull/6710) - Restore `rsync` output into the workflow reinstallation log.

[#6711](https://github.com/cylc/cylc-flow/pull/6711) - Stop broadcast allowing `[remote]host` if `platform` set, or vice-versa

[#6721](https://github.com/cylc/cylc-flow/pull/6721) - Fixed a bug that could mark satisfied xtriggers as unsatisfied after a restart, in task queries.

[#6722](https://github.com/cylc/cylc-flow/pull/6722) - Fix a slow memory leak in Tui.

[#6727](https://github.com/cylc/cylc-flow/pull/6727) - Fixed a memory leak affecting both scheduler and UI server.

[#6733](https://github.com/cylc/cylc-flow/pull/6733) - Fix an issue where the message "Cannot tell if the workflow is running" error could appear erroneously.

[#6745](https://github.com/cylc/cylc-flow/pull/6745) - Fixed a bug affecting `cylc play` with run hosts specified in the global config, but no ranking expression specified.

[#6758](https://github.com/cylc/cylc-flow/pull/6758) - Fixes an issue where not all in-window graph edges were being generated.

## __cylc-8.4.2 (Released 2025-04-07)__

### 🔧 Fixes

[#6169](https://github.com/cylc/cylc-flow/pull/6169) - Ensure that job submit/failure is logged, even when retries are planned.

[#6583](https://github.com/cylc/cylc-flow/pull/6583) - Fix bug where undefined outputs were missed by validation if no tasks trigger off of them.

[#6589](https://github.com/cylc/cylc-flow/pull/6589) - Fix potential accumulation of old families in UI.

[#6623](https://github.com/cylc/cylc-flow/pull/6623) - Auto restart: The option to condemn a host in "force" mode (that tells
  workflows running on a server to shutdown as opposed to migrate) hasn't worked
  with the host-selection mechanism since Cylc 8.0.0. This has now been fixed.

[#6638](https://github.com/cylc/cylc-flow/pull/6638) - Fixed possible crash when restarting a workflow after changing the graph.

[#6639](https://github.com/cylc/cylc-flow/pull/6639) - Ensure that shutdown event handlers are killed if they exceed the process pool timeout.

[#6645](https://github.com/cylc/cylc-flow/pull/6645) - Fixed a typo in stop.py which caused a different exception to be raised than was desired

[#6647](https://github.com/cylc/cylc-flow/pull/6647) - Ensure `cylc message` exceptions are printed to `job.err`.

[#6656](https://github.com/cylc/cylc-flow/pull/6656) - Fix bug where old cycle points could accumulate in the UI.

[#6658](https://github.com/cylc/cylc-flow/pull/6658) - Fixed `cylc reinstall` not picking up file permissions changes.

[#6691](https://github.com/cylc/cylc-flow/pull/6691) - Fix bug in the `cylc set` command: attempting to set invalid prerequisites on
  a future task could prevent it from spawning later on.

## __cylc-8.4.1 (Released 2025-02-25)__

### 🔧 Fixes

[#6480](https://github.com/cylc/cylc-flow/pull/6480) - `cat-log`: List log files which are available via a configured tailer/viewer command.

[#6506](https://github.com/cylc/cylc-flow/pull/6506) - Work around caching behaviour observed on NFS filesystems which could cause workflows to appear to be stopped or even to not exist, when they are running.

[#6518](https://github.com/cylc/cylc-flow/pull/6518) - Allow setting empty values in `flow.cylc[scheduler][events]` to override the global configuration.

[#6535](https://github.com/cylc/cylc-flow/pull/6535) - Ensure tasks can be killed while in the preparing state.

[#6551](https://github.com/cylc/cylc-flow/pull/6551) - Fix bug in `cylc lint` S014 where it warned about use of legitimate `-W` directive for PBS.

[#6571](https://github.com/cylc/cylc-flow/pull/6571) - Disabled PEP-515-style integer coercion of task parameters containing underscores (e.g. `084_132` was becoming `84132`). This fix returns older behaviour seen in Cylc 7.

[#6577](https://github.com/cylc/cylc-flow/pull/6577) - Fixed a bug where if you prematurely deleted the job log directory, it would leave tasks permanently in the submitted or running states.

[#6578](https://github.com/cylc/cylc-flow/pull/6578) - Improved handling of any internal errors when executing commands against a running workflow.

[#6586](https://github.com/cylc/cylc-flow/pull/6586) - Update PBS job runner to reflect error message change. This change
  continues to support older PBS versions.

[#6616](https://github.com/cylc/cylc-flow/pull/6616) - Fixed wrapper script `PATH` override preventing selection of Cylc version in the GUI when running Cylc Hub.

## __cylc-8.4.0 (Released 2025-01-08)__

### ⚠ Breaking Changes

[#6476](https://github.com/cylc/cylc-flow/pull/6476) - Remove support for the EmPy template engine.

### 🚀 Enhancements

[#6039](https://github.com/cylc/cylc-flow/pull/6039) - Added a new task run mode "skip" in which tasks instantly generate their required outputs without actually running. This allows us to configure tasks to "skip" ahead of time, e.g. to skip a cycle of tasks that is no longer needed.

[#6137](https://github.com/cylc/cylc-flow/pull/6137) - New Cylc lint rule: S014: Don't use job runner specific execution time limit directives, use execution time limit.

[#6168](https://github.com/cylc/cylc-flow/pull/6168) - Allow symlinking log/job separately from log

[#6289](https://github.com/cylc/cylc-flow/pull/6289) - Made the errors resulting from Jinja2 `raise` and `assert` statements more straight forward.

[#6440](https://github.com/cylc/cylc-flow/pull/6440) - The "cylc dump" command now prints task IDs. Use "--legacy" if you need the old format.

[#6444](https://github.com/cylc/cylc-flow/pull/6444) - The scheduler now traps the SIGINT, SIGTERM and SIGHUP signals and will respond by shutting down in --now mode. If the workflow is already shutting down in --now mode, it will escalate the shutdown to --now --now mode.

[#6456](https://github.com/cylc/cylc-flow/pull/6456) - `cylc lint` now checks for unnecessary continuation characters in the graph section.

[#6472](https://github.com/cylc/cylc-flow/pull/6472) - `cylc remove` improvements:
  - It can now remove tasks that are no longer active, making it look like they never ran.
  - Removing a submitted/running task will kill it.
  - Added the `--flow` option.
  - Removed tasks are now demoted to `flow=none` but retained in the workflow database for provenance.

[#6475](https://github.com/cylc/cylc-flow/pull/6475) - Allow easy definition of multiple install targets in `global.cylc[install][symlink dirs]` using comma separated lists.

[#6491](https://github.com/cylc/cylc-flow/pull/6491) - The "cylc show" command now says if the target task is held, queued, or runahead limited.

[#6499](https://github.com/cylc/cylc-flow/pull/6499) - Manually triggered tasks now run immediately even if the workflow is paused.

### 🔧 Fixes

[#6081](https://github.com/cylc/cylc-flow/pull/6081) - Fix job submission when a batch of jobs is submitted to a runner that does
  not return a newline with the job ID (did not affect built-in job runners).

[#6511](https://github.com/cylc/cylc-flow/pull/6511) - cat-log command list-dir mode: fail gracefully if directory not found.

[#6526](https://github.com/cylc/cylc-flow/pull/6526) - Output optionality validation now checks tasks with cycle offsets.

[#6528](https://github.com/cylc/cylc-flow/pull/6528) - Make start-tasks wait on xtriggers (see "cylc play --start-task").

## __cylc-8.3.6 (Released 2024-11-07)__

### 🔧 Fixes

[#4983](https://github.com/cylc/cylc-flow/pull/4983) - Ensure the runahead limit is recomputed when legacy "suicide-triggers" are used, to prevent erroneous stall in niche cases.

[#6263](https://github.com/cylc/cylc-flow/pull/6263) - Fix bug that prevented changes to user-defined xtriggers taking effect after a reload.

[#6326](https://github.com/cylc/cylc-flow/pull/6326) - Fix a rare issue where missing job records could cause tasks to become stuck in active states.

[#6364](https://github.com/cylc/cylc-flow/pull/6364) - Fixed bug where `cylc clean <workflow> --rm share` would not take care of removing the target of the `share/cycle` symlink directory.

[#6376](https://github.com/cylc/cylc-flow/pull/6376) - Fixes an issue that could cause Cylc to ignore the remaining hosts in a platform in response to an `ssh` error in some niche circumstances.

[#6388](https://github.com/cylc/cylc-flow/pull/6388) - Fix task state filtering in Tui.

[#6414](https://github.com/cylc/cylc-flow/pull/6414) - Broadcast will now reject truncated cycle points to aviod runtime errors.

[#6422](https://github.com/cylc/cylc-flow/pull/6422) - Enabled jumping to the top/bottom of log files in Tui using the "home" and "end" keys.

[#6431](https://github.com/cylc/cylc-flow/pull/6431) - The `cycle point format` was imposing an undesirable constraint on `wall_clock` offsets, this has been fixed.

[#6433](https://github.com/cylc/cylc-flow/pull/6433) - Ignore requests to trigger or set active tasks with --flow=none.

[#6445](https://github.com/cylc/cylc-flow/pull/6445) - Ensure `cylc trigger` does not fall back to `flow=none` when there are no active flows.

[#6448](https://github.com/cylc/cylc-flow/pull/6448) - Fix the non-spawning of parentless sequential xtriggered tasks when outputs are set.

## __cylc-8.3.5 (Released 2024-10-15)__

### 🔧 Fixes

[#6316](https://github.com/cylc/cylc-flow/pull/6316) - Fixed bug in `cylc vr` where an initial cycle point of `now`/`next()`/`previous()` would result in an error.

[#6362](https://github.com/cylc/cylc-flow/pull/6362) - Fixed simulation mode bug where the task submit number would not increment

[#6367](https://github.com/cylc/cylc-flow/pull/6367) - Fix bug where `cylc trigger` and `cylc set` would assign active flows to existing tasks by default.

[#6397](https://github.com/cylc/cylc-flow/pull/6397) - Fix "dictionary changed size during iteration error" which could occur with broadcasts.

## __cylc-8.3.4 (Released 2024-09-12)__

### 🚀 Enhancements

[#6266](https://github.com/cylc/cylc-flow/pull/6266) - 'cylc show' task output is now sorted by the task id

### 🔧 Fixes

[#6175](https://github.com/cylc/cylc-flow/pull/6175) - The workflow-state command and xtrigger will now reject invalid polling arguments.

[#6214](https://github.com/cylc/cylc-flow/pull/6214) - `cylc lint` rules U013 & U015 now tell you which deprecated variables you are using

[#6264](https://github.com/cylc/cylc-flow/pull/6264) - Fix bug where `cylc install` failed to prevent invalid run names.

[#6267](https://github.com/cylc/cylc-flow/pull/6267) - Fixed bug in `cylc play` affecting run host reinvocation after interactively upgrading the workflow to a new Cylc version.

[#6310](https://github.com/cylc/cylc-flow/pull/6310) - Fix a spurious traceback that could occur when running the `cylc play` command on Mac OS.

[#6330](https://github.com/cylc/cylc-flow/pull/6330) - Fix bug where broadcasting failed to change platform selected after host selection failure.

[#6332](https://github.com/cylc/cylc-flow/pull/6332) - Fixes unformatted string

[#6335](https://github.com/cylc/cylc-flow/pull/6335) - Fix an issue that could cause broadcasts made to multiple namespaces to fail.

[#6337](https://github.com/cylc/cylc-flow/pull/6337) - Fix potential duplicate job submissions when manually triggering unqueued active tasks.

[#6345](https://github.com/cylc/cylc-flow/pull/6345) - Fix duplicate job submissions of tasks in the preparing state before reload.

[#6351](https://github.com/cylc/cylc-flow/pull/6351) - Fix a bug where simulation mode tasks were not spawning children of task:started.

[#6353](https://github.com/cylc/cylc-flow/pull/6353) - Prevent clock-expired tasks from being automatically retried.

## __cylc-8.3.3 (Released 2024-07-23)__

### 🔧 Fixes

[#6103](https://github.com/cylc/cylc-flow/pull/6103) - Absolute dependencies (dependencies on tasks in a specified cycle rather than at a specified offset) are now visible in the GUI beyond the specified cycle.

[#6213](https://github.com/cylc/cylc-flow/pull/6213) - Fix bug where the `-S`, `-O` and `-D` options in `cylc vr` would not be applied correctly when restarting a workflow.

[#6241](https://github.com/cylc/cylc-flow/pull/6241) - Allow flow-merge when triggering n=0 tasks.

[#6242](https://github.com/cylc/cylc-flow/pull/6242) - Put `share/bin` in the `PATH` of scheduler environment, event handlers therein will now be found.

[#6249](https://github.com/cylc/cylc-flow/pull/6249), [#6252](https://github.com/cylc/cylc-flow/pull/6252) - Fix a race condition between global config reload and debug logging that caused "platform not defined" errors when running workflows that contained a "rose-suite.conf" file in verbose or debug mode.

## __cylc-8.3.2 (Released 2024-07-10)__

### 🔧 Fixes

[#6186](https://github.com/cylc/cylc-flow/pull/6186) - Fixed bug where using flow numbers with `cylc set` would not work correctly.

[#6200](https://github.com/cylc/cylc-flow/pull/6200) - Fixed bug where a stalled paused workflow would be incorrectly reported as running, not paused

[#6206](https://github.com/cylc/cylc-flow/pull/6206) - Fixes the spawning of multiple parentless tasks off the same sequential wall-clock xtrigger.

## __cylc-8.3.1 (Released 2024-07-04)__

### 🔧 Fixes

[#6130](https://github.com/cylc/cylc-flow/pull/6130) - Prevent commands accepting job IDs where it doesn't make sense.

[#6170](https://github.com/cylc/cylc-flow/pull/6170) - Fix an issue where the Cylc logo could appear in the workflow log.

[#6176](https://github.com/cylc/cylc-flow/pull/6176) - Fix bug where jobs which fail to submit are not shown in GUI/TUI if submission retries are set.

[#6178](https://github.com/cylc/cylc-flow/pull/6178) - Fix an issue where Tui could hang when closing.

## __cylc-8.3.0 (Released 2024-06-18)__

### ⚠ Breaking Changes

[#5600](https://github.com/cylc/cylc-flow/pull/5600) - The `cylc dump` command now only shows active tasks (e.g. running & queued
  tasks). This restores its behaviour of only showing the tasks which currently
  exist in the pool as it did in Cylc 7 and earlier versions of Cylc 8.

[#5727](https://github.com/cylc/cylc-flow/pull/5727) - Cylc now ignores `PYTHONPATH` to make it more robust to task environments which set this value. If you want to add to the Cylc environment itself, e.g. to install a Cylc extension, use `CYLC_PYTHONPATH`.

[#5794](https://github.com/cylc/cylc-flow/pull/5794) - Remove `cylc report-timings` from automatic installation with `pip install cylc-flow[all]`. If you now wish to install it use `pip install cylc-flow[report-timings]`. `cylc report-timings` is incompatible with Python 3.12.

[#5836](https://github.com/cylc/cylc-flow/pull/5836) - Removed the 'CYLC_TASK_DEPENDENCIES' environment variable

[#5956](https://github.com/cylc/cylc-flow/pull/5956) - `cylc lint`: deprecated `[cylc-lint]` section in favour of `[tool.cylc.lint]` in `pyproject.toml`

[#6046](https://github.com/cylc/cylc-flow/pull/6046) - The `submit-fail` and `expire` task outputs must now be
  [optional](https://cylc.github.io/cylc-doc/stable/html/glossary.html#term-optional-output)
  and can no longer be
  [required](https://cylc.github.io/cylc-doc/stable/html/glossary.html#term-required-output).

### 🚀 Enhancements

[#5571](https://github.com/cylc/cylc-flow/pull/5571) - Make workflow `CYLC_` variables available to the template processor during parsing.

[#5658](https://github.com/cylc/cylc-flow/pull/5658) - New "cylc set" command for setting task prerequisites and outputs.

[#5709](https://github.com/cylc/cylc-flow/pull/5709) - Forward arbitrary environment variables over SSH connections

[#5721](https://github.com/cylc/cylc-flow/pull/5721) - Allow task simulation mode settings to be changed dynamically using `cylc broadcast`.

[#5731](https://github.com/cylc/cylc-flow/pull/5731) - Major upgrade to `cylc tui` which now supports larger workflows and can browse installed workflows.

[#5738](https://github.com/cylc/cylc-flow/pull/5738) - Optionally spawn parentless xtriggered tasks sequentially - i.e., one at a time, after the previous xtrigger is satisfied, instead of all at once out to the runahead limit. The `wall_clock` xtrigger is now sequential by default.

[#5769](https://github.com/cylc/cylc-flow/pull/5769) - Include task messages and workflow port as appropriate in emails configured by "mail events".

[#5803](https://github.com/cylc/cylc-flow/pull/5803) - Updated 'reinstall' functionality to support multiple workflows

[#5809](https://github.com/cylc/cylc-flow/pull/5809) - The workflow-state command and xtrigger are now flow-aware and take universal IDs instead of separate arguments for cycle point, task name, etc. (which are still supported, but deprecated).

[#5831](https://github.com/cylc/cylc-flow/pull/5831) - Add capability to install xtriggers via a new cylc.xtriggers entry point

[#5864](https://github.com/cylc/cylc-flow/pull/5864) - Reimplemented the `suite-state` xtrigger for interoperability with Cylc 7.

[#5872](https://github.com/cylc/cylc-flow/pull/5872) - Improvements to `cylc clean` remote timeout handling.

[#5873](https://github.com/cylc/cylc-flow/pull/5873) - `cylc lint` improvements:
  - Allow use of `#noqa: S001` comments to skip checks for a single line.
  - Stop `cylc lint` objecting to `%include <file>` syntax.

[#5879](https://github.com/cylc/cylc-flow/pull/5879) - `cylc lint` now warns of use of old templated items such as `%(suite)s`

[#5890](https://github.com/cylc/cylc-flow/pull/5890) - Lint: Warn users that setting ``CYLC_VERSION``, ``ROSE_VERSION`` or
  ``FCM_VERSION`` in the workflow config is deprecated.

[#5943](https://github.com/cylc/cylc-flow/pull/5943) - The `stop after cycle point` can now be specified as an offset from the inital cycle point.

[#5955](https://github.com/cylc/cylc-flow/pull/5955) - Support xtrigger argument validation.

[#6029](https://github.com/cylc/cylc-flow/pull/6029) - Workflow graph window extent is now preserved on reload.

[#6046](https://github.com/cylc/cylc-flow/pull/6046) - The condition that Cylc uses to evaluate task output completion can now be
  customized in the `[runtime]` section with the new `completion` configuration.
  This provides a more advanced way to check that tasks generate their required
  outputs when run.

### 🔧 Fixes

[#5809](https://github.com/cylc/cylc-flow/pull/5809) - Fix bug where the "cylc workflow-state" command only polled for
  task-specific status queries and custom outputs.

[#6008](https://github.com/cylc/cylc-flow/pull/6008) - Fixed bug where the `[scheduler][mail]to/from` settings did not apply as defaults for task event mail.

[#6036](https://github.com/cylc/cylc-flow/pull/6036) - Fixed bug in simulation mode where repeated submissions were not displaying correctly in TUI/GUI.

[#6067](https://github.com/cylc/cylc-flow/pull/6067) - Fixed a bug that sometimes allowed suicide-triggered or manually removed tasks to be added back later.

[#6109](https://github.com/cylc/cylc-flow/pull/6109) - Fixed bug affecting job submission where the list of bad hosts was not always reset correctly.

[#6123](https://github.com/cylc/cylc-flow/pull/6123) - Allow long-format datetime cycle points in IDs used on the command line.

## __cylc-8.2.7 (Released 2024-05-15)__

### 🔧 Fixes

[#6096](https://github.com/cylc/cylc-flow/pull/6096) - Fixed bug that caused graph arrows to go missing in the GUI when suicide triggers are present.

[#6102](https://github.com/cylc/cylc-flow/pull/6102) - Fixed bug introduced in 8.2.6 in `cylc vip` & `cylc vr` when using cylc-rose options (`-S`, `-D`, `-O`).

## __cylc-8.2.6 (Released 2024-05-02)__

### ⚠ Breaking Changes

[#6068](https://github.com/cylc/cylc-flow/pull/6068) - Removed the Rose Options (`-S`, `-O`, `-D`) from `cylc play`. If you need these use them with `cylc install`.

### 🚀 Enhancements

[#6072](https://github.com/cylc/cylc-flow/pull/6072) - Nano Syntax Highlighting now available.

### 🔧 Fixes

[#6071](https://github.com/cylc/cylc-flow/pull/6071) - `cylc config` now shows xtrigger function signatures.

[#6078](https://github.com/cylc/cylc-flow/pull/6078) - Fixed bug where `cylc lint` could hang when checking `inherit` settings in `flow.cylc`.

## __cylc-8.2.5 (Released 2024-04-04)__

### 🔧 Fixes

[#5924](https://github.com/cylc/cylc-flow/pull/5924) - Validation: a cycle offset can only appear on the right of a dependency if the task's cycling is defined elsewhere with no offset.

[#5933](https://github.com/cylc/cylc-flow/pull/5933) - Fixed bug in `cylc broadcast` (and the GUI Edit Runtime command) where everything after a `#` character in a setting would be stripped out.

[#5959](https://github.com/cylc/cylc-flow/pull/5959) - Fix an issue where workflow "timeout" events were not fired in all situations when they should have been.

[#6011](https://github.com/cylc/cylc-flow/pull/6011) - Fixed a `cylc vip` bug causing remote re-invocation to fail if using `--workflow-name` option.

[#6031](https://github.com/cylc/cylc-flow/pull/6031) - Fixed workflow-state command and xtrigger for alternate cylc-run directory.

## __cylc-8.2.4 (Released 2024-01-11)__

### 🚀 Enhancements

[#5772](https://github.com/cylc/cylc-flow/pull/5772) - `cylc lint`: added a check for indentation being 4N spaces.

[#5838](https://github.com/cylc/cylc-flow/pull/5838) - `cylc lint`: added rule to check for `rose date` usage (should be replaced with `isodatetime`).

### 🔧 Fixes

[#5789](https://github.com/cylc/cylc-flow/pull/5789) - Prevent the run mode from being changed on restart.

[#5801](https://github.com/cylc/cylc-flow/pull/5801) - Fix traceback when using parentheses on right hand side of graph trigger.

[#5821](https://github.com/cylc/cylc-flow/pull/5821) - Fixed issue where large uncommitted changes could cause `cylc install` to hang.

[#5841](https://github.com/cylc/cylc-flow/pull/5841) - `cylc lint`: improved handling of S011 to not warn if the `#` is `#$` (e.g. shell base arithmetic).

[#5885](https://github.com/cylc/cylc-flow/pull/5885) - Fixed bug in using a final cycle point with chained offsets e.g. 'final cycle point = +PT6H+PT1S'.

[#5893](https://github.com/cylc/cylc-flow/pull/5893) - Fixed bug in computing a time interval-based runahead limit when future triggers are present.

[#5902](https://github.com/cylc/cylc-flow/pull/5902) - Fixed a bug that prevented unsetting `execution time limit` by broadcast or reload.

[#5908](https://github.com/cylc/cylc-flow/pull/5908) - Fixed bug causing redundant DB updates when many tasks depend on the same xtrigger.

[#5909](https://github.com/cylc/cylc-flow/pull/5909) - Fix a bug where Cylc VIP did not remove --workflow-name=<name> from
  Cylc play arguments.

## __cylc-8.2.3 (Released 2023-11-02)__

### 🔧 Fixes

[#5660](https://github.com/cylc/cylc-flow/pull/5660) - Re-worked graph n-window algorithm for better efficiency.

[#5753](https://github.com/cylc/cylc-flow/pull/5753) - Fixed bug where execution time limit polling intervals could end up incorrectly applied

[#5776](https://github.com/cylc/cylc-flow/pull/5776) - Ensure that submit-failed tasks are marked as incomplete (so remain visible) when running in back-compat mode.

[#5791](https://github.com/cylc/cylc-flow/pull/5791) - fix a bug where if multiple clock triggers are set for a task only one was being satisfied.

## __cylc-8.2.2 (Released 2023-10-05)__

### 🚀 Enhancements

[#5237](https://github.com/cylc/cylc-flow/pull/5237) - Back-compat: allow workflow-state xtriggers (and the `cylc workflow-state`
  command) to read Cylc 7 databases.

### 🔧 Fixes

[#5693](https://github.com/cylc/cylc-flow/pull/5693) - Log command issuer, if not the workflow owner, for all commands.

[#5694](https://github.com/cylc/cylc-flow/pull/5694) - Don't fail config file parsing if current working directory does not exist.
  (Note however this may not be enough to prevent file parsing commands failing
  elsewhere in the Python library).

[#5704](https://github.com/cylc/cylc-flow/pull/5704) - Fix off-by-one error in automatic upgrade of Cylc 7 "max active cycle points" to Cylc 8 "runahead limit".

[#5708](https://github.com/cylc/cylc-flow/pull/5708) - Fix runahead limit at start-up, with recurrences that start beyond the limit.

[#5755](https://github.com/cylc/cylc-flow/pull/5755) - Fixes an issue where submit-failed tasks could be incorrectly considered as completed rather than causing the workflow to stall.


## __cylc-8.2.1 (Released 2023-08-14)__

### 🔧 Fixes

[#5631](https://github.com/cylc/cylc-flow/pull/5631) - Fix bug in remote clean for workflows that generated `flow.cylc` files at runtime.

[#5650](https://github.com/cylc/cylc-flow/pull/5650) - Fix a bug preventing clean-up of finished tasks in the GUI and TUI.

[#5685](https://github.com/cylc/cylc-flow/pull/5685) - Fix "cylc pause" command help (it targets workflows, not tasks, but was
  printing task-matching documentation as well).


## __cylc-8.2.0 (<span actions:bind='release-date'>Released 2023-07-21</span>)__

### Breaking Changes

[#5600](https://github.com/cylc/cylc-flow/pull/5600) -
The `CYLC_TASK_DEPENDENCIES` environment variable will no longer be exported
in job environments if there are more than 50 dependencies. This avoids an
issue which could cause jobs to fail if this variable became too long.

### Enhancements

[#5992](https://github.com/cylc/cylc-flow/pull/5992) -
Before trying to reload the workflow definition, the scheduler will
now wait for preparing tasks to submit, and pause the workflow.
After successful reload the scheduler will unpause the workflow.

[#5605](https://github.com/cylc/cylc-flow/pull/5605) - Added `-z` shorthand
option for defining a list of strings:
- Before: `cylc command -s "X=['a', 'bc', 'd']"`
- After: `cylc command -z X=a,bc,d`.

[#5537](https://github.com/cylc/cylc-flow/pull/5537) - Allow parameters
in family names to be split, e.g. `<foo>FAM<bar>`.

[#5589](https://github.com/cylc/cylc-flow/pull/5589) - Move to workflow
directory during file parsing, to give the template processor access to
workflow files.

[#5405](https://github.com/cylc/cylc-flow/pull/5405) - Improve scan command
help, and add scheduler PID to the output.

[#5461](https://github.com/cylc/cylc-flow/pull/5461) - preserve colour
formatting when starting workflows in distributed mode using `run hosts`.

[#5291](https://github.com/cylc/cylc-flow/pull/5291) - re-implement old-style
clock triggers as wall_clock xtriggers.

[#5439](https://github.com/cylc/cylc-flow/pull/5439) - Small CLI short option chages:
Add the `-n` short option for `--workflow-name` to `cylc vip`; rename the `-n`
short option for `--no-detach` to `-N`; add `-r` as a short option for
`--run-name`.

[#5231](https://github.com/cylc/cylc-flow/pull/5231) - stay up for a timeout
period on restarting a completed workflow, to allow for manual triggering.

[#5549](https://github.com/cylc/cylc-flow/pull/5549),
[#5546](https://github.com/cylc/cylc-flow/pull/5546) -
Various enhancements to `cylc lint`:
* `cylc lint` will provide a non-zero return code if any issues are identified.
  This can be overridden using the new `--exit-zero` flag.
* Fix numbering of lint codes (n.b. lint codes should now be permenantly
  unchanging, but may have changed since Cylc 8.1.4, so `pyproject.toml` files
  may need updating).
* Check for suicide triggers in `.cylc` files.
* Check for `platform = $(rose host-select)`.
* Check for use of deprecated Cylc commands (and `rose suite-hook`).
* Check for zero prefixed Jinja2 integers.
* Only check for missing Jinja2 shebangs in `flow.cylc` and
  `suite.rc` files.


[#5525](https://github.com/cylc/cylc-flow/pull/5525) - Jobs can use scripts
in `share/bin` and Python modules in `share/lib/python`.

### Fixes

[#5328](https://github.com/cylc/cylc-flow/pull/5328) -
Efficiency improvements to reduce task management overheads on the Scheduler.

[#5611](https://github.com/cylc/cylc-flow/pull/5611) -
Improve the documentation of the GraphQL schema.

[#5616](https://github.com/cylc/cylc-flow/pull/5616) -
Improve PBS support for job IDs with trailing components.

[#5619](https://github.com/cylc/cylc-flow/pull/5619) -
Fix an issue where the `task_pool` table in the database wasn't being updated
in a timely fashion when tasks completed.

[#5606](https://github.com/cylc/cylc-flow/pull/5606) -
Task outputs and messages are now validated to avoid conflicts with built-in
outputs, messages, qualifiers and Cylc keywords.

[#5614](https://github.com/cylc/cylc-flow/pull/5614) -
Fix a bug in Cylc 7 compatibility mode where tasks running in the `none` flow
(e.g. via `cylc trigger --flow=none`) would trigger downstream tasks.

[#5604](https://github.com/cylc/cylc-flow/pull/5604) -
Fix a possible issue where workflows started using
`cylc play --start-cycle-point` could hang during startup.

[#5573](https://github.com/cylc/cylc-flow/pull/5573) - Fix bug that ran a
queued waiting task even after removal by `cylc remove`.

[#5524](https://github.com/cylc/cylc-flow/pull/5524) - Logging includes timestamps
for `cylc play` when called by `cylc vip` or `cylc vr`.

[#5228](https://github.com/cylc/cylc-flow/pull/5228) -
Enabled the "stop", "poll", "kill" and "message" commands to be issued from
the UI whilst the workflow is in the process of shutting down.

[#5582](https://github.com/cylc/cylc-flow/pull/5582) - Set Cylc 7 compatibility
mode before running pre-configure plugins.

[#5587](https://github.com/cylc/cylc-flow/pull/5587) -
Permit commas in xtrigger arguments and fix minor issues with the parsing of
xtrigger function signatures.

[#5618](https://github.com/cylc/cylc-flow/pull/5618) -
Fix a bug when rapidly issuing the same/opposite commands e.g. pausing &
resuming a workflow.

[#5625](https://github.com/cylc/cylc-flow/pull/5625) - Exclude `setuptools`
version (v67) which results in dependency check failure with editable installs.

## __cylc-8.1.4 (<span actions:bind='release-date'>Released 2023-05-04</span>)__

### Fixes

[#5514](https://github.com/cylc/cylc-flow/pull/5514) -
Ensure `cylc cat-log` directory listings always include the `job-activity.log`
file when present and are able to list submit-failed jobs.

[#5506](https://github.com/cylc/cylc-flow/pull/5506) -
Fix bug introduced in 8.1.3 where specifying a subshell command for
`flow.cylc[runtime][<namespace>][remote]host` (e.g. `$(rose host-select)`)
would always result in localhost.

## __cylc-8.1.3 (<span actions:bind='release-date'>Released 2023-04-27</span>)__

### Enhancements

[#5475](https://github.com/cylc/cylc-flow/pull/5475) - much faster computation
of the visualization window around active tasks (at the cost, for now, of not
showing non-active "cousin" nodes).

[#5453](https://github.com/cylc/cylc-flow/pull/5453) - `cylc cat-log` can now
list and view workflow log files including install logs and workflow
configuration files.

### Fixes

[#5495](https://github.com/cylc/cylc-flow/pull/5495) - Fix bug that could cause
invalid parent tasks to appear in the UI datastore.

[#5334](https://github.com/cylc/cylc-flow/pull/5334) - Apply graph prerequisite
changes to already-spawned tasks after reload or restart.

[5466](https://github.com/cylc/cylc-flow/pull/5466) - Don't generate duplicate
prerequisites from recurrences with coincident points.

[5450](https://github.com/cylc/cylc-flow/pull/5450) - Validation provides
better error messages if [sections] and settings are mixed up in a
configuration.

[5445](https://github.com/cylc/cylc-flow/pull/5445) - Fix remote tidy
 bug where install target is not explicit in platform definition.

[5398](https://github.com/cylc/cylc-flow/pull/5398) - Fix platform from
group selection order bug.

[#5395](https://github.com/cylc/cylc-flow/pull/5395) - Fix bug where workflow
shuts down if all hosts for all platforms in a platform group are unreachable.

[#5384](https://github.com/cylc/cylc-flow/pull/5384) -
Fixes `cylc set-verbosity`.

[#5479](https://github.com/cylc/cylc-flow/pull/5479) -
Fixes `cylc help license`

[#5394](https://github.com/cylc/cylc-flow/pull/5394) -
Fixes a possible scheduler traceback observed with remote task polling.

[#5386](https://github.com/cylc/cylc-flow/pull/5386) - Fix bug where
absence of `job name length maximum` in PBS platform settings would cause
Cylc to crash when preparing the job script.

[#5343](https://github.com/cylc/cylc-flow/pull/5343) - Fix a bug causing
platform names to be checked as if they were hosts.

[#5359](https://github.com/cylc/cylc-flow/pull/5359) - Fix bug where viewing
a workflow's log in the GUI or using `cylc cat-log` would prevent `cylc clean`
from working.

## __cylc-8.1.2 (<span actions:bind='release-date'>Released 2023-02-20</span>)__

### Fixes

[#5349](https://github.com/cylc/cylc-flow/pull/5349) - Bugfix: `cylc vip --workflow-name`
only worked when used with a space, not an `=`.

[#5367](https://github.com/cylc/cylc-flow/pull/5367) - Enable using
Rose options (`-O`, `-S` & `-D`) with `cylc view`.

[#5363](https://github.com/cylc/cylc-flow/pull/5363) Improvements and bugfixes
for `cylc lint`.

## __cylc-8.1.1 (<span actions:bind='release-date'>Released 2023-01-31</span>)__

### Fixes

[#5313](https://github.com/cylc/cylc-flow/pull/5313) - Fix a bug
causing Cylc to be unable to parse previously played Cylc 7 workflows.

[#5312](https://github.com/cylc/cylc-flow/pull/5312) - task names must be
comma-separated in queue member lists. Any implicit tasks
(i.e. with no task definition under runtime) assigned to a queue will generate a warning.

[#5314](https://github.com/cylc/cylc-flow/pull/5314) - Fix broken
command option: `cylc vip --run-name`.

[#5319](https://github.com/cylc/cylc-flow/pull/5319),
[#5321](https://github.com/cylc/cylc-flow/pull/5321),
[#5325](https://github.com/cylc/cylc-flow/pull/5325) -
Various efficiency optimisations to the scheduler which particularly impact
workflows with many-to-many dependencies (e.g. `<a> => <b>`).

## __cylc-8.1.0 (<span actions:bind='release-date'>Released 2023-01-16</span>)__

### Breaking Changes

* Workflows started with Cylc 8.0 which contain multiple "flows" cannot be
  restarted with Cylc 8.1 due to database changes.

### Enhancements

[#5229](https://github.com/cylc/cylc-flow/pull/5229) -
- Added a single command to validate a previously run workflow against changes
  to its source and reinstall a workflow.
- Allows Cylc commands (including validate, list, view, config, and graph) to load template variables
  configured by `cylc install` and `cylc play`.

[#5121](https://github.com/cylc/cylc-flow/pull/5121) - Added a single
command to validate, install and play a workflow.

[#5184](https://github.com/cylc/cylc-flow/pull/5184) - Scan for active
runs of the same workflow at install time.

[#5084](https://github.com/cylc/cylc-flow/pull/5084) - Assign the most recent
previous flow numbers to tasks triggered when no flows are present (e.g. on
restarting a finished workflow).

[#5032](https://github.com/cylc/cylc-flow/pull/5032) - Set a default limit of
100 for the "default" queue.

[#5055](https://github.com/cylc/cylc-flow/pull/5055) and
[#5086](https://github.com/cylc/cylc-flow/pull/5086) - Upgrades to `cylc lint`
- Allow users to ignore Cylc Lint issues using `--ignore <Issue Code>`.
- Allow settings for `cylc lint` to be recorded in a pyproject.toml file.
- Allow files to be excluded from `cylc lint` checks.

[#5081](https://github.com/cylc/cylc-flow/pull/5081) - Reduced amount that
gets logged at "INFO" level in scheduler logs.

[#5259](https://github.com/cylc/cylc-flow/pull/5259) - Add flow_nums
to task_jobs table in the workflow database.

### Fixes

[#5286](https://github.com/cylc/cylc-flow/pull/5286) - Fix bug where
`[scheduling][special tasks]clock-trigger` would skip execution retry delays.

[#5292](https://github.com/cylc/cylc-flow/pull/5292) -
Fix an issue where polling could be repeated if the job's platform
was not available.

## __cylc-8.0.4 (<span actions:bind='release-date'>Released 2022-12-14</span>)__

Maintenance release.

### Fixes

[##5205](https://github.com/cylc/cylc-flow/pull/#5205) - Fix bug which caused
orphaned running tasks to silently skip remote file installation at scheduler restart.

[#5224](https://github.com/cylc/cylc-flow/pull/5225) - workflow installation:
disallow reserved names only in the top level source directory.

[#5211](https://github.com/cylc/cylc-flow/pull/5211) - Provide better
explanation of failure if `icp = next (T-02, T-32)` when list should be
semicolon separated.

[#5196](https://github.com/cylc/cylc-flow/pull/5196) - Replace traceback
with warning, for scan errors where workflow is stopped.

[#5199](https://github.com/cylc/cylc-flow/pull/5199) - Fix a problem with
the consolidation tutorial.

[#5195](https://github.com/cylc/cylc-flow/pull/5195) -
Fix issue where workflows can fail to shutdown due to unavailable remote
platforms and make job log retrieval more robust.

## __cylc-8.0.3 (<span actions:bind='release-date'>Released 2022-10-17</span>)__

Maintenance release.

### Fixes

[#5192](https://github.com/cylc/cylc-flow/pull/5192) -
Recompute runahead limit after use of `cylc remove`.

[#5188](https://github.com/cylc/cylc-flow/pull/5188) -
Fix task state selectors in `cylc trigger` and other commands.

[#5125](https://github.com/cylc/cylc-flow/pull/5125) - Allow rose-suite.conf
changes to be considered by ``cylc reinstall``.

[#5023](https://github.com/cylc/cylc-flow/pull/5023),
[#5187](https://github.com/cylc/cylc-flow/pull/5187) -
tasks force-triggered
after a shutdown was ordered should submit to run immediately on restart.

[#5137](https://github.com/cylc/cylc-flow/pull/5137) -
Install the `ana/` directory to remote platforms by default.

[#5146](https://github.com/cylc/cylc-flow/pull/5146) - no-flow tasks should not
retrigger incomplete children.

[#5104](https://github.com/cylc/cylc-flow/pull/5104) - Fix retriggering of
failed tasks after a reload.

[#5139](https://github.com/cylc/cylc-flow/pull/5139) - Fix bug where
`cylc install` could hang if there was a large uncommitted diff in the
source dir (for git/svn repos).

[#5131](https://github.com/cylc/cylc-flow/pull/5131) - Infer workflow run number
for `workflow_state` xtrigger.

## __cylc-8.0.2 (<span actions:bind='release-date'>Released 2022-09-12</span>)__

Maintenance release.

### Fixes

[#5115](https://github.com/cylc/cylc-flow/pull/5115) - Updates rsync commands
to make them compatible with latest rsync releases.

[#5119](https://github.com/cylc/cylc-flow/pull/5119) - Fix formatting of
deprecation warnings at validation.

[#5067](https://github.com/cylc/cylc-flow/pull/5067) - Datastore fix for
taskdefs removed before restart.

[#5066](https://github.com/cylc/cylc-flow/pull/5066) - Fix bug where
.cylcignore only found if `cylc install` is run in source directory.

[#5091](https://github.com/cylc/cylc-flow/pull/5091) - Fix problems with
tutorial workflows.

[#5098](https://github.com/cylc/cylc-flow/pull/5098) - Fix bug where final task
status updates were not being sent to UI before shutdown.

[#5114](https://github.com/cylc/cylc-flow/pull/5114) - Fix bug where
validation errors during workflow startup were not printed to stderr before
daemonisation.

[#5110](https://github.com/cylc/cylc-flow/pull/5110) - Fix bug where reloading
a stalled workflow would cause it stall again.

## __cylc-8.0.1 (<span actions:bind='release-date'>Released 2022-08-16</span>)__

Maintenance release.

### Fixes

[#5025](https://github.com/cylc/cylc-flow/pull/5025) - Fix a bug where polling
causes a failed task to be shown as submitted when the workflow is reloaded.

[#5045](https://github.com/cylc/cylc-flow/pull/5045) -
Fix issue where unsatisfied xtriggers could be wiped on reload.

[#5031](https://github.com/cylc/cylc-flow/pull/5031) - Fix bug where
specifying multiple datetime offsets (e.g. `final cycle point = +P1M-P1D`)
would not obey the given order.

[#5033](https://github.com/cylc/cylc-flow/pull/5033) - Running `cylc clean`
on a top level dir containing run dir(s) will now remove that top level dir
in addition to the run(s) (if there is nothing else inside it).

[#5007](https://github.com/cylc/cylc-flow/pull/5007) - Fix for `cylc broadcast`
cycle point validation in the UI.

[#5037](https://github.com/cylc/cylc-flow/pull/5037) - Fix bug where the
workflow restart number would get wiped on reload.

[#5049](https://github.com/cylc/cylc-flow/pull/5049) - Fix several small
bugs related to auto restart.

[#5062](https://github.com/cylc/cylc-flow/pull/5062) - Fix bug where preparing
tasks could sometimes get orphaned when an auto restart occurred.

## __cylc-8.0.0 (<span actions:bind='release-date'>Released 2022-07-28</span>)__

Cylc 8 production-ready release.

### Major Changes

* Python 2 -> 3.
* Internal communications converted from HTTPS to ZMQ (TCP).
* PyGTK GUIs replaced by:
  * Terminal user interface (TUI) included in cylc-flow.
  * Web user interface provided by the cylc-uiserver package.
* A new scheduling algorithm with support for branched workflows.
* Command line changes:
  * `cylc run` -> `cylc play`
  * `cylc restart` -> `cylc play`
  * `rose suite-run` -> `cylc install; cylc play <id>`
* The core package containing Cylc scheduler program has been renamed cylc-flow.
* Cylc review has been removed, the Cylc 7 version remains Cylc 8 compatible.
* [New documentation](https://cylc.github.io/cylc-doc/stable).

See the [migration guide](https://cylc.github.io/cylc-doc/stable/html/7-to-8/index.html) for a full list of changes.

### Enhancements

[#4964](https://github.com/cylc/cylc-flow/pull/4964) -
`cylc reinstall` now displays the changes it would make when run
interactively and has improved help / documentaiton.

[#4836](https://github.com/cylc/cylc-flow/pull/4836) - The log directory has
been tidied. Workflow logs are now found in `log/scheduler` rather than
`log/workflow`, filenames now include `start`/`restart`. Other minor directory
changes. Remote file installation logs are now per install target.

[#4938](https://github.com/cylc/cylc-flow/pull/4938) - Detect bad Platforms
config: background and at job runners should have a single host.

[#4877](https://github.com/cylc/cylc-flow/pull/4877) - Upgrade the version of
Jinja2 used by Cylc from 2.11 to 3.0.

[#4896](https://github.com/cylc/cylc-flow/pull/4896) - Allow the setting of
default job runner directives for platforms.

[#4900](https://github.com/cylc/cylc-flow/pull/4900) - Added a command to assist
with upgrading Cylc 7 workflows to Cylc 8: Try `cylc lint <workflow-dir>`.

[#5009](https://github.com/cylc/cylc-flow/pull/5009) - Added new job
environment variable `$CYLC_WORKFLOW_NAME_BASE` as the basename of
`$CYLC_WORKFLOW_NAME`.

[#4993](https://github.com/cylc/cylc-flow/pull/4993) - Remove the few remaining
uses of a configured text editor (via `cylc view` and `cylc cat-log` options).
The primary uses of it (`cylc trigger --edit` and `cylc edit` in Cylc 7) have
already been removed from Cylc 8.

### Fixes

[#5011](https://github.com/cylc/cylc-flow/pull/5011) - Removes preparing jobs
appearing in UI, and reuse submit number on restart for preparing tasks.

[#5008](https://github.com/cylc/cylc-flow/pull/5008) -
Autospawn absolute-triggered tasks exactly the same way as parentless tasks.

[#4984](https://github.com/cylc/cylc-flow/pull/4984) -
Fixes an issue with `cylc reload` which could cause preparing tasks to become
stuck.

[#4976](https://github.com/cylc/cylc-flow/pull/4976) - Fix bug causing tasks
to be stuck in UI due to discontinued graph of optional outputs.

[#4975](https://github.com/cylc/cylc-flow/pull/4975) - Fix selection of
platforms from `[job]` and `[remote]` configs.

[#4948](https://github.com/cylc/cylc-flow/pull/4948) - Fix lack of
errors/warnings for deprecated `[runtime][<task>][remote]retrieve job logs *`
settings.

[#4970](https://github.com/cylc/cylc-flow/pull/4970) - Fix handling of suicide
triggers in back-compat mode.

[#4887](https://github.com/cylc/cylc-flow/pull/4887) - Disallow relative paths
in `global.cylc[install]source dirs`.

[#4906](https://github.com/cylc/cylc-flow/pull/4906)
- Fix delayed spawning of parentless tasks that do have parents in a previous
  cycle point.
- Make integer-interval runahead limits consistent with time-interval limits:
  `P0` means just the runahead base point; `P1` the base point and the point
  (i.e. one cycle interval), and so on.

[#4936](https://github.com/cylc/cylc-flow/pull/4936) - Fix incorrect
error messages when workflow CLI commands fail.

[#4941](https://github.com/cylc/cylc-flow/pull/4941) - Fix job state for
platform submit-failures.

[#4931](https://github.com/cylc/cylc-flow/pull/4931) - Fix cylc install for
installing workflows from multi-level directories.

[#4926](https://github.com/cylc/cylc-flow/pull/4926) - Fix a docstring
formatting problem presenting in the UI mutation flow argument info.

[#4891](https://github.com/cylc/cylc-flow/pull/4891) - Fix bug that could cause
past jobs to be omitted in the UI.

[#4860](https://github.com/cylc/cylc-flow/pull/4860) - Workflow validation
now fails if
[owner setting](https://cylc.github.io/cylc-doc/stable/html/reference/config/workflow.html#flow.cylc[runtime][%3Cnamespace%3E][remote]owner)
is used, as that setting no longer has any effect.

[#4978](https://github.com/cylc/cylc-flow/pull/4978) - `cylc clean`: fix
occasional failure to clean on remote hosts due to leftover contact file.

[#4889](https://github.com/cylc/cylc-flow/pull/4889) - `cylc clean`: don't
prompt if no matching workflows.

[#4890](https://github.com/cylc/cylc-flow/pull/4890) - `cylc install`: don't
overwrite symlink dir targets if they were not cleaned properly before.

[#4881](https://github.com/cylc/cylc-flow/pull/4881) - Fix bug where commands
targeting a specific cycle point would not work if using an abbreviated
cycle point format.


## Older Releases

* [Cylc 7 changelog](https://github.com/cylc/cylc-flow/blob/7.8.x/CHANGES.md)
* [Cylc 8 pre-release changelog](https://github.com/cylc/cylc-flow/blob/8.0.0/CHANGES.md)
