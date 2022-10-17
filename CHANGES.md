# Selected Cylc Changes

Internal changes that do not directly affect users may not be listed here.  For
all changes see the [closed
milestones](https://github.com/cylc/cylc-flow/milestones?state=closed) for each
release.

## Major Changes in Cylc 8

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

<!-- The topmost release date is automatically updated by GitHub Actions. When
creating a new release entry be sure to copy & paste the span tag with the
`actions:bind` attribute, which is used by a regex to find the text to be
updated. Only the first match gets replaced, so it's fine to leave the old
ones in. -->

-------------------------------------------------------------------------------
## __cylc-8.0.3 (<span actions:bind='release-date'>Released 2022-10-17</span>)__

Maintenance release.

### Fixes

[#5192](https://github.com/cylc/cylc-flow/pull/5192) - Recompute runahead limit
after use of `cylc remove`.

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

-------------------------------------------------------------------------------
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

-------------------------------------------------------------------------------
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

-------------------------------------------------------------------------------
## __cylc-8.0.0 (<span actions:bind='release-date'>Released 2022-07-28</span>)__

Cylc 8 production-ready release.

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

-------------------------------------------------------------------------------
## __cylc-8.0rc3 (<span actions:bind='release-date'>Released 2022-05-19</span>)__

Third Release Candidate for Cylc 8 suitable for acceptance testing.

### Enhancements

[#4738](https://github.com/cylc/cylc-flow/pull/4738) and
[#4739](https://github.com/cylc/cylc-flow/pull/4739) - Implement `cylc trigger
[--flow=] [--wait]` for manual triggering with respect to active flows (the
default), specific flows, new flows, or one-off task runs. This replaces
the `--reflow` option from earlier pre-release versions.

[#4743](https://github.com/cylc/cylc-flow/pull/4743) - On stopping a specific
flow, remove active-waiting tasks with no remaining flow numbers.

[#4854](https://github.com/cylc/cylc-flow/pull/4854)
- Expansion and merger of comma separated platform definitions permitted.
- Platform definition regular expressions which match "localhost" but are not
  "localhost" are now explicitly forbidden and will raise an exception.

[#4842](https://github.com/cylc/cylc-flow/pull/4842) -
Improve Jinja2 error reporting when the error is behind an `{% include`.

[#4861](https://github.com/cylc/cylc-flow/pull/4861) - Allow workflow source
 directories to be under `cylc-run`.

[#4828](https://github.com/cylc/cylc-flow/pull/4828) - scan CLI: corrupt
workflow contact files should result in a warning, not a crash.

[#4823](https://github.com/cylc/cylc-flow/pull/4823) - Remove the `--directory`
option for `cylc install` (the functionality has been merged into the
workflow source argument), and rename the `--flow-name` option to
`--workflow-name`.

### Fixes

[#4873](https://github.com/cylc/cylc-flow/pull/4873) - `cylc show`: don't
show prerequisites of past tasks recalled from the DB as unsatisfied.

[#4875](https://github.com/cylc/cylc-flow/pull/4864) - Fix the file name
pattern matching used for emacs syntax highlighting.

[#4864](https://github.com/cylc/cylc-flow/pull/4864) - Allow strings
and more complex data type template variables to be stored correctly
in the workflow database.

[#4863](https://github.com/cylc/cylc-flow/pull/4863) - Execution timeout is no
longer set based on execution time limit. Fixes bug where execution timeout
would get overridden.

[#4844](https://github.com/cylc/cylc-flow/pull/4844) - Fixes bug where
execution polling intervals used in combination with an execution time limit
resulted in incorrect polling intervals.

[#4829](https://github.com/cylc/cylc-flow/pull/4829) -
Suppress deprecated configuration warnings in Cylc 7 compatibility mode.

[#4830](https://github.com/cylc/cylc-flow/pull/4830) -
Workflow scan now detects Cylc 7 suites installed, but not yet run, by Cylc 8.

[#4554](https://github.com/cylc/cylc-flow/pull/4554) - Fix incorrect
implementation of the ISO 8601 recurrence format no. 1
(`R<number>/<start-point>/<second-point>`)
(see [metomi/isodatetime#45](https://github.com/metomi/isodatetime/issues/45)).
This recurrence format was not mentioned in the Cylc documentation, so
this is unlikely to affect you.

[#4748](https://github.com/cylc/cylc-flow/pull/4748) -
`cylc tui` gives a more helpful error message when a workflow is not running;
distinguishing between workflow not running and not in run-directory.

[#4797](https://github.com/cylc/cylc-flow/pull/4797) -
`cylc reload` now triggers a fresh remote file installation for all relevant
platforms, any files configured to be installed will be updated on the remote
platform.

[#4791](https://github.com/cylc/cylc-flow/pull/4791) - Fix bug where task
outputs would not show up in the UI.

[#4777](https://github.com/cylc/cylc-flow/pull/4777) -
Reinstate the Cylc 7 template variables for xtriggers with deprecation warnings.

[#4771](https://github.com/cylc/cylc-flow/pull/4771) -
Fix issue where Cylc 7 workflows could show in `cylc scan` output and in the UI.

[#4720](https://github.com/cylc/cylc-flow/pull/4720) - Fix traceback in
workflow logs when starting or reloading a workflow with an illegal item
(e.g. typo) in the config.

[#4827](https://github.com/cylc/cylc-flow/pull/4827) - Fix bug where specifying
an invalid `--stopcp` would corrupt the workflow database. Also fix
inconsistency between how `[scheduling]stop after cycle point` was handled
on reload/restart compared to the other cycle point settings.

[#4872](https://github.com/cylc/cylc-flow/pull/4872) - Fix bug preventing
`cylc clean <workflow_name>/runN` from working.

[#4769](https://github.com/cylc/cylc-flow/pull/4769) - Fix handling of quoted
command args for invocation on remote run hosts.


-------------------------------------------------------------------------------
## __cylc-8.0rc2 (<span actions:bind='release-date'>Released 2022-03-23</span>)__

Second Release Candidate for Cylc 8 suitable for acceptance testing.

### Enhancements

[#4736](https://github.com/cylc/cylc-flow/pull/4736) - `rsync` command used for
remote file installation is now configurable.

[#4655](https://github.com/cylc/cylc-flow/pull/4655) - Enhancements to the
provided [wrapper script](https://cylc.github.io/cylc-doc/stable/html/installation.html#managing-environments).

### Fixes

[#4703](https://github.com/cylc/cylc-flow/pull/4703) - Fix `ImportError` when
validating/running a Jinja2 workflow (for users who have installed Cylc
using `pip`.)

[#4745](https://github.com/cylc/cylc-flow/pull/4745) - Fix traceback when
running `cylc help all` without optional dependencies installed.

[#4670](https://github.com/cylc/cylc-flow/pull/4670) - Fix several TUI bugs.

[#4730](https://github.com/cylc/cylc-flow/pull/4730) - Fix bug on the command
line when specifying a Cylc ID that includes your username (e.g. `'~user/workflow'`).

[#4737](https://github.com/cylc/cylc-flow/pull/4737) -
Fix issue which prevented tasks with incomplete outputs from being rerun by
subsequent flows.

-------------------------------------------------------------------------------
## __cylc-8.0rc1 (<span actions:bind='release-date'>Released 2022-02-17</span>)__

First Release Candidate for Cylc 8 suitable for acceptance testing.

Cylc 8 beta users will not be able to restart workflows run with previous
Cylc 8 pre-releases due to changes in the workflow database structure
([#4581](https://github.com/cylc/cylc-flow/pull/4581))

### Enhancements

[#4581](https://github.com/cylc/cylc-flow/pull/4581) - Improvements allowing
the UI & TUI to remember more info about past tasks and jobs:
- Job and task history is now loaded into the window about active tasks.
- Reflow future tasks now set to waiting.

[#3931](https://github.com/cylc/cylc-flow/pull/3931) - Convert Cylc to
use the new "Universal Identifier".

[#3931](https://github.com/cylc/cylc-flow/pull/3931),
[#4675](https://github.com/cylc/cylc-flow/pull/4675) - `cylc clean` now
interactively prompts if trying to clean multiple run dirs.

[#4506](https://github.com/cylc/cylc-flow/pull/4506) - Cylc no longer
creates a `flow.cylc` symlink to a `suite.rc` file.
This only affects you if you have used a prior Cylc 8 pre-release.

[#4547](https://github.com/cylc/cylc-flow/pull/4547) - The max scan depth is
now configurable in `global.cylc[install]max depth`, and `cylc install` will
fail if the workflow ID would exceed this depth.

[#4534](https://github.com/cylc/cylc-flow/pull/4534) - Permit jobs
to be run on platforms with no `$HOME` directory.

[#4536](https://github.com/cylc/cylc-flow/pull/4536) - `cylc extract-resources`
renamed `cylc get-resources` and small changes made:
- Cylc wrapper script made available.
- Source argument now before target.
- Metadata as well as names from ``--list`` option.
- Files extracted to ``target/source_name`` rather than ``target/full/source/path``.

[#4548](https://github.com/cylc/cylc-flow/pull/4548) - Changed the
workflow version control info log file format from modified-INI to JSON.

[#4521](https://github.com/cylc/cylc-flow/pull/4521) - The workflow config
logs (that get written in `log/flow-config/` on start/restart/reload)
are now sparse, i.e. they will no longer be fleshed-out with defaults.

[#4558](https://github.com/cylc/cylc-flow/pull/4558) -
Added a metadata section to the platform and platform group configurations.

[#4561](https://github.com/cylc/cylc-flow/pull/4561) - Moved the tutoral
workflow back into Cylc from Cylc Docs to make it a packaged resource for
anyone with a Cylc installation.

[#4576](https://github.com/cylc/cylc-flow/pull/4576) - Added
`--platform-names` and `--platforms` options to `cylc config` for easy
access to information on configured platforms.

### Fixes

[#4658](https://github.com/cylc/cylc-flow/pull/4658) -
Don't poll waiting tasks (which may have the submit number of a previous job).

[#4620](https://github.com/cylc/cylc-flow/pull/4620) -
Fix queue interactions with the scheduler paused and task held states.

[#4667](https://github.com/cylc/cylc-flow/pull/4667) - Check manually triggered
tasks are not already preparing for job submission.

[#4640](https://github.com/cylc/cylc-flow/pull/4640) - Fix manual triggering of
runahead-limited parentless tasks.

[#4645](https://github.com/cylc/cylc-flow/pull/4645) - Fix behaviour when a
flow catches up to a running force-triggered no-flow task.

[#4566](https://github.com/cylc/cylc-flow/pull/4566) - Fix `cylc scan`
invocation for remote scheduler host on a shared filesystem.

[#4511](https://github.com/cylc/cylc-flow/pull/4511) - Fix clock xtriggers for
large inexact offsets (year, months); restore time check for old-style
(task-property) clock triggers.

[#4568](https://github.com/cylc/cylc-flow/pull/4568) - Disable all CLI colour
output if not to a terminal.

[#4553](https://github.com/cylc/cylc-flow/pull/4553) - Add job submit time
to the datastore.

[#4526](https://github.com/cylc/cylc-flow/pull/4526) - Prevent `runN` and
`run<number>` being allowed as installation target names.

[#4526](https://github.com/cylc/cylc-flow/pull/4526),
[#4549](https://github.com/cylc/cylc-flow/pull/4549) - Prevent installing
workflows with directory names that include reserved filenames such as
`log`, `work`, `runN`, `run<number>` etc.

[#4442](https://github.com/cylc/cylc-flow/pull/4442) - Prevent installation
of workflows inside other installed workflows.

[#4540](https://github.com/cylc/cylc-flow/pull/4540) - Handle the `/` character
in job names, for PBS 19.2.1+.

[#4570](https://github.com/cylc/cylc-flow/pull/4570) - Fix incorrect fallback
to localhost if `[runtime][<task>][remote]host` is unreachable.

[#4543](https://github.com/cylc/cylc-flow/pull/4543) -
`cylc play --stopcp=reload` now takes its value from
`[scheduling]stop after cycle point` instead of using the final cycle point.


-------------------------------------------------------------------------------
## __cylc-8.0b3 (<span actions:bind='release-date'>Released 2021-11-10</span>)__

Fourth beta release of Cylc 8.

(See note on cylc-8 backward-incompatible changes, above)

### Enhancements

[#4355](https://github.com/cylc/cylc-flow/pull/4355) -
The `--workflow-owner` command line option has been removed.

[#4367](https://github.com/cylc/cylc-flow/pull/4367) -
Make the central wrapper work with arbitrary virtual environment names.

[#4343](https://github.com/cylc/cylc-flow/pull/4343) -
Implement required and optional outputs with new graph notation.

[#4324](https://github.com/cylc/cylc-flow/pull/4324) -
Re-implement a basic form of the Cylc 7 `cylc graph` command for static
graph visualisation.

[#4335](https://github.com/cylc/cylc-flow/pull/4335) -
Have validation catch erroneous use of both `expr => bar` and `expr => !bar` in
the same graph.

[#4285](https://github.com/cylc/cylc-flow/pull/4285) - Cylc now automatically
infers the latest numbered run of the workflow for most commands (e.g. you can
run `cylc pause foo` instead of having to type out `foo/run3`).

[#4346](https://github.com/cylc/cylc-flow/pull/4346) -
Use natural sort order for the `cylc scan --sort` option.

[#4313](https://github.com/cylc/cylc-flow/pull/4313) - Change `ignore` to
`reload` for the cycle point cli options (e.g. `--fcp=reload`), as this more
accurately reflects what it's doing. Also improve validation of these
cli options.

[#4389](https://github.com/cylc/cylc-flow/pull/4389) - the `flow.cylc.processed`
(previously called `suite.rc.processed`) is now stored in `log/flow-config/`.

[#4329](https://github.com/cylc/cylc-flow/pull/4329) - Enable selection of
platform from platform group at task job initialization.

[#4430](https://github.com/cylc/cylc-flow/pull/4430) - Log files renamed:
- `log/flow.cylc.processed` ⇒ `log/flow-processed.cylc`
- `log/<datetimes>-run.cylc` ⇒ `log/<datetimes>-start.cylc`

[#4423](https://github.com/cylc/cylc-flow/pull/4423) - Only changes to the
workflow directory are recorded by `log/version`.

[#4404](https://github.com/cylc/cylc-flow/pull/4404) - The Cylc Graph section
now accepts ``&`` and ``|`` as valid line breaks in the same way as ``=>``.

[#4455](https://github.com/cylc/cylc-flow/pull/4455) - `CYLC_WORKFLOW_NAME`
renamed to `CYLC_WORKFLOW_ID`. `CYLC_WORKFLOW_NAME` re-added as
`CYLC_WORKFLOW_ID` shorn of any trailing `runX`.

[#4471](https://github.com/cylc/cylc-flow/pull/4471) - Users now get a different
error for a config item that isn't valid, to one that isn't set.

[#4457](https://github.com/cylc/cylc-flow/pull/4457) - Cylc 8
`cycle point time zone` now defaults to UTC, except in Cylc 7 compatibility mode.

### Fixes

[#4493](https://github.com/cylc/cylc-flow/pull/4493) - handle late job
submission message properly.

[#4443](https://github.com/cylc/cylc-flow/pull/4443) - fix for slow polling
generating an incorrect submit-failed result.

[#4436](https://github.com/cylc/cylc-flow/pull/4436) -
If the workflow is paused, hold tasks just before job prep.
Distinguish between succeeded and expired state icons in `cylc tui`.
Spawn parentless tasks out the runahead limit immediately.

[#4421](https://github.com/cylc/cylc-flow/pull/4421) -
Remove use of the `ps` system call (fixes a bug reported with Alpine Linux).

[#4426](https://github.com/cylc/cylc-flow/pull/4426) -
Fix bug when a conditional expression in the graph contains one task name that
is a substring of another.

[#4399](https://github.com/cylc/cylc-flow/pull/4399) -
Ensure that implicit task names are validated (as opposed to explicit ones).

[#4341](https://github.com/cylc/cylc-flow/pull/4341) -
Remove obsolete Cylc 7 `[scheduling]spawn to max active cycle points` config.

[#4319](https://github.com/cylc/cylc-flow/pull/4319) -
Update cylc reinstall to skip cylc dirs work and share

[#4289](https://github.com/cylc/cylc-flow/pull/4289) - Make `cylc clean`
safer by preventing cleaning of dirs that contain more than one workflow
run dir (use `--force` to override this safeguard).

[#4362](https://github.com/cylc/cylc-flow/pull/4362) -
When using `cylc clean` on a sequential run directory, remove the `runN` symlink
if it points to the removed directory.

[#4395](https://github.com/cylc/cylc-flow/pull/4362) -
Fix ``cylc stop --kill`` which was not actually killing task jobs.

[#4338](https://github.com/cylc/cylc-flow/pull/4338) - Cylc install -C option
now works with relative paths.

[#4440](https://github.com/cylc/cylc-flow/pull/4440) -
Fix an error that could occur during remote clean and other `cylc clean`
improvements.

[#4481](https://github.com/cylc/cylc-flow/pull/4481) -
Removed non-functional ping command from GUI.

[#4445](https://github.com/cylc/cylc-flow/pull/4445) - Cylc will prevent you
using the same name for a platform and a platform group. Which one it should
pick is ambiguous, and is a setup error.

[#4465](https://github.com/cylc/cylc-flow/pull/4465) -
Fix a `ValueError` that could occasionally occur during remote tidy on
workflow shutdown.

-------------------------------------------------------------------------------
## __cylc-8.0b2 (<span actions:bind='release-date'>Released 2021-07-28</span>)__

Third beta release of Cylc 8.

(See note on cylc-8 backward-incompatible changes, above)

### Enhancements

[#4286](https://github.com/cylc/cylc-flow/pull/4286) -
Add an option for displaying source workflows in `cylc scan`.

[#4300](https://github.com/cylc/cylc-flow/pull/4300) - Integer flow labels with
flow metadata, and improved task logging.

[#4291](https://github.com/cylc/cylc-flow/pull/4291) -
Remove obsolete `cylc edit` and `cylc search` commands.

[#4284](https://github.com/cylc/cylc-flow/pull/4284) -
Make `--color=never` work with `cylc <command> --help`.

[#4259](https://github.com/cylc/cylc-flow/pull/4259) -
Ignore pre-initial dependencies with `cylc play --start-task`

[#4103](https://github.com/cylc/cylc-flow/pull/4103) -
Expose runahead limiting to UIs; restore correct force-triggering of queued
tasks for Cylc 8.

[#4250](https://github.com/cylc/cylc-flow/pull/4250) -
Symlink dirs localhost symlinks are now overridable with cli option
`--symlink-dirs`.

[#4218](https://github.com/cylc/cylc-flow/pull/4218) - Add ability to
start a new run from specified tasks instead of a cycle point.

[#4214](https://github.com/cylc/cylc-flow/pull/4214) -
Unify `-v --verbose`, `-q --quiet` and `--debug` options.

[#4174](https://github.com/cylc/cylc-flow/pull/4174) - Terminology: replace
"suite" with "workflow".

[#4177](https://github.com/cylc/cylc-flow/pull/4177) - Remove obsolete
configuration items from `global.cylc[platforms][<platform name>]`:
`run directory`, `work directory` and `suite definition directory`. This
functionality is now provided by `[symlink dirs]`.

[#4142](https://github.com/cylc/cylc-flow/pull/4142) - Record source directory
version control information on installation of a workflow.

[#4238](https://github.com/cylc/cylc-flow/pull/4238) - Future tasks can now
be held in advance using `cylc hold` (previously it was only active tasks
that could be held).

[#4237](https://github.com/cylc/cylc-flow/pull/4237) - `cylc clean` can now
remove specific sub-directories instead of the whole run directory, using the
`--rm` option. There are also the options `--local-only` and `--remote-only`
for choosing to only clean on the local filesystem or remote install targets
respectively.

### Fixes

[#4296](https://github.com/cylc/cylc-flow/pull/4296) -
Patches DNS issues with newer versions of Mac OS.

[#4273](https://github.com/cylc/cylc-flow/pull/4273) -
Remove obsolete Cylc 7 visualization config section.

[#4272](https://github.com/cylc/cylc-flow/pull/4272) - Workflow visualisation
data (data-store) now constrained by final cycle point.

[#4248](https://github.com/cylc/cylc-flow/pull/4248) -
Fix parameter expansion in inherited task environments.

[#4227](https://github.com/cylc/cylc-flow/pull/4227) - Better error messages
when initial cycle point is not valid for the cycling type.

[#4228](https://github.com/cylc/cylc-flow/pull/4228) - Interacting with a
workflow on the cli using `runN` is now supported.

[#4193](https://github.com/cylc/cylc-flow/pull/4193) - Standard `cylc install`
now correctly installs from directories with a `.` in the name. Symlink dirs
now correctly expands environment variables on the remote. Fixes minor cosmetic
bugs.

[#4199](https://github.com/cylc/cylc-flow/pull/4199) -
`cylc validate` and `cylc run` now check task/family names in the `[runtime]`
section for validity.

[#4180](https://github.com/cylc/cylc-flow/pull/4180) - Fix bug where installing
a workflow that uses the deprecated `suite.rc` filename would symlink `flow.cylc`
to the `suite.rc` in the source dir instead of the run dir. Also fixes a couple
of other, small bugs.

[#4222](https://github.com/cylc/cylc-flow/pull/4222) - Fix bug where a
workflow's public database file was not closed properly.

-------------------------------------------------------------------------------
## __cylc-8.0b1 (<span actions:bind='release-date'>Released 2021-04-21</span>)__

Second beta release of Cylc 8.

(See note on cylc-8 backward-incompatible changes, above)

### Enhancements

[#4154](https://github.com/cylc/cylc-flow/pull/4154) -
Deprecate `CYLC_SUITE_DEF_PATH` with `CYLC_SUITE_RUN_DIR` (note the deprecated
variable is still present in the job environment).

[#4164](https://github.com/cylc/cylc-flow/pull/4164) -
Replace the job "host" field with "platform" in the GraphQL schema.

### Fixes

[#4169](https://github.com/cylc/cylc-flow/pull/4169) -
Fix a host ⇒ platform upgrade bug where host names were being popped from task
configs causing subsequent tasks to run on localhost.

[#4173](https://github.com/cylc/cylc-flow/pull/4173) -
Fix the state totals shown in both the UI and TUI, including incorrect counts
during workflow run and post pause.

[#4168](https://github.com/cylc/cylc-flow/pull/4168) - Fix bug where any
errors during workflow shutdown were not logged.

[#4161](https://github.com/cylc/cylc-flow/pull/4161) - Fix bug in `cylc install`
where a workflow would be installed with the wrong name.

[#4188](https://github.com/cylc/cylc-flow/pull/4188) - Fix incorrect usage
examples for `cylc install`.

-------------------------------------------------------------------------------
## __cylc-8.0b0 (<span actions:bind='release-date'>Released 2021-03-29</span>)__

First beta release of Cylc 8.

(See note on cylc-8 backward-incompatible changes, above)

The filenames `suite.rc` and `global.rc` are now deprecated in favour of
`flow.cylc` and `global.cylc` respectively
([#3755](https://github.com/cylc/cylc-flow/pull/3755)). For backward
compatibility, the `cylc run` command will automatically symlink an existing
`suite.rc` file to `flow.cylc`.

Obsolete *queued* task state replaced by *waiting*, with a queued flag;
queueing logic centralized.
([#4088](https://github.com/cylc/cylc-flow/pull/4088)).

`cylc register` has been replaced by `cylc install`
([#4000](https://github.com/cylc/cylc-flow/pull/4000)).

Added a new command: `cylc clean`, for removing stopped workflows on the local
and any remote filesystems ([#3961](https://github.com/cylc/cylc-flow/pull/3961),
[#4017](https://github.com/cylc/cylc-flow/pull/4017)).

`cylc run` and `cylc restart` have been replaced by `cylc play`, simplifying
how workflows are restarted
([#4040](https://github.com/cylc/cylc-flow/pull/4040)).

`cylc pause` and `cylc play` are now used to pause and resume workflows,
respectively. `cylc hold` and `cylc release` now only hold and release tasks,
not the whole workflow. ([#4076](https://github.com/cylc/cylc-flow/pull/4076))

"Implicit"/"naked" tasks (tasks that do not have an explicit definition in
`flow.cylc[runtime]`) are now disallowed by default
([#4109](https://github.com/cylc/cylc-flow/pull/4109)). You can allow them by
setting `flow.cylc[scheduler]allow implicit tasks` to `True`.

Named checkpoints have been removed ([#3906](https://github.com/cylc/cylc-flow/pull/3906))
due to being a seldom-used feature. Workflows can still be restarted from the
last run, or reflow can be used to achieve the same result.

### Enhancements

[#4119](https://github.com/cylc/cylc-flow/pull/4119) - Reimplement ssh task
communications.

[#4115](https://github.com/cylc/cylc-flow/pull/4115) - Raise an error when
invalid sort keys are provided clients.

[#4105](https://github.com/cylc/cylc-flow/pull/4105) - Replace the
`cylc executable` global config setting with `cylc path`, for consistency with
`cylc` invocation in job scripts.

[#4014](https://github.com/cylc/cylc-flow/pull/4014) - Rename "ready" task
state to "preparing".

[#4000](https://github.com/cylc/cylc-flow/pull/4000) - `cylc install` command
added. Install workflows into cylc run directory from source directories
configured in `global.cylc` (see [#4132](https://github.com/cylc/cylc-flow/pull/4132)),
or from arbitrary locations.

[#4071](https://github.com/cylc/cylc-flow/pull/4071) - `cylc reinstall` command
added.

[#3992](https://github.com/cylc/cylc-flow/pull/3992) - Rename
batch system to job runner.

[#3791](https://github.com/cylc/cylc-flow/pull/3791) - Support Slurm
heterogeneous jobs with a special directive prefix.

[#3974](https://github.com/cylc/cylc-flow/pull/3974) - Template variables,
both in set files and provided via the -s/--set command line options are
now parsed using ast.literal_eval. This permits non-string data types,
strings must now be quoted.

[#3811](https://github.com/cylc/cylc-flow/pull/3811) - Move from cycle based
to `n` distance dependency graph window node generation and pruning of the
data-store (API/visual backing data). Ability to modify distance of live
workflow via API, with default of `n=1`.

[#3899](https://github.com/cylc/cylc-flow/pull/3899) - CLI changes
* Commands no longer re-invoke (so you get `cylc run` not `cylc-run`).
* Improve CLI descriptions and help.
* Internal-only commands now hidden from help.
* New entry point for defining Cylc sub-commands.
* remove `cylc check-software` (use standard tools like pipdeptree)
* remove `cylc nudge` (no longer needed)

[#3884](https://github.com/cylc/cylc-flow/pull/3884) - Directories `run`,
`log`, `share`, `share/cycle`, `work` now have the option to be redirected to
configured directories by symlink.

[#3856](https://github.com/cylc/cylc-flow/pull/3856) - fail the GraphQL query
with a helpful message if the variables defined do not match the expected
values.

[#3853](https://github.com/cylc/cylc-flow/pull/3853) - Update protobuf and
pyzmq.

[#3857](https://github.com/cylc/cylc-flow/pull/3857) - removed the obsolete
"runahead" task state (not used since spawn-on-demand implementation).

[#3816](https://github.com/cylc/cylc-flow/pull/3816) - change `cylc spawn`
command name to `cylc set-outputs` to better reflect its role in Cylc 8.

[#3796](https://github.com/cylc/cylc-flow/pull/3796) - Remote installation is
now on a per install target rather than a per platform basis. `app/`, `bin/`,
`etc/`, `lib/` directories are now installed on the target, configurable in flow.cylc.

[#3724](https://github.com/cylc/cylc-flow/pull/3724) - Re-implemented
the `cylc scan` command line interface and added a Python API for accessing
workflow scanning functionality.

[#3515](https://github.com/cylc/cylc-flow/pull/3515) - spawn-on-demand: a more
efficient way of the evolving the workflow via the graph.

[#3692](https://github.com/cylc/cylc-flow/pull/3692) - Use the `$EDITOR`
and `$GEDITOR` environment variables to determine the default editor to use.

[#3574](https://github.com/cylc/cylc-flow/pull/3574) - use the bash
installation defined in $path rather than hardcoding to /bin/bash.

[#3774](https://github.com/cylc/cylc-flow/pull/3774) - Removed support for
interactive prompt.

[#3798](https://github.com/cylc/cylc-flow/pull/3798) - Deprecated the
`[runtime][X][parameter environment templates]` section and instead allow
templates in `[runtime][X][environment]`.

[#3802](https://github.com/cylc/cylc-flow/pull/3802) - New global config
hierarchy and ability to set site config directory.

[#3848](https://github.com/cylc/cylc-flow/pull/3848) - Deprecated
`[scheduling]max active cycle points` in favour of `[scheduling]runahead limit`.

[#3883](https://github.com/cylc/cylc-flow/pull/3883) - Added a new workflow
config option `[scheduling]stop after cycle point`.

[#3913](https://github.com/cylc/cylc-flow/pull/3913) - Added the ability to
use plugins to parse suite templating variables and additional files to
install. Only one such plugin exists at the time of writing, designed to
parse ``rose-suite.conf`` files in repository "cylc-rose".

[#3955](https://github.com/cylc/cylc-flow/pull/3955) - Global config options
to control the job submission environment.

[#4020](https://github.com/cylc/cylc-flow/pull/4020) - `cylc validate` will no
longer check for a cyclic/circular graph if there are more than 100 tasks,
unless the option  `--check-circular` is used. This is to improve performance.

[#3913](https://github.com/cylc/cylc-flow/pull/3913) - Add ability to use
pre-install entry point from cylc-rose plugin to provide environment and
template variables for a workflow.

[#4023](https://github.com/cylc/cylc-flow/pull/4023) - Add ability to use
post-install entry point from cylc-rose to use Rose style CLI settings of
configurations in Cylc install. If Cylc-rose is installed three new CLI
options will be available:
- `--opt_conf_keys="foo, bar"`
- `--defines="[env]FOO=BAR"`
- `--suite-defines="FOO=BAR"`

[#4101](https://github.com/cylc/cylc-flow/pull/4101) - Add the ability to
ignore (clear) rose install options from an earlier install:
`cylc reinstall --clear-rose-install-options`

[#4094](https://github.com/cylc/cylc-flow/pull/4094) - Prevent Cylc from
rsyncing the following files on install and reinstall:
- `rose-suite.conf`
- `opt/rose-suite-cylc-install.conf`
These files should be handled by the cylc-rose plugin if you require them.

[#4126](https://github.com/cylc/cylc-flow/pull/4126) - Make obsolete the config
``flow.cylc:[runtime][__TASK__][remote]suite definition directory``.

[#4098](https://github.com/cylc/cylc-flow/pull/4098) - Provide a dictionary called
CYLC_TEMPLATE_VARS into the templating environment.

[#4099](https://github.com/cylc/cylc-flow/pull/4099) - Unify `cylc get-suite-config`
and `cylc get-site-config` commands as `cylc config`. Some options have been
removed.

### Fixes

[#3984](https://github.com/cylc/cylc-flow/pull/3984) - Only write task
event timers to the database when they have changed (reverts behaviour
change in 7.8.6). This corrects last updated db entries and reduces filesystem
load.

[#3917](https://github.com/cylc/cylc-flow/pull/3917) - Fix a bug that caused
one of the hostname resolution tests to fail in certain environments.

[#3879](https://github.com/cylc/cylc-flow/pull/3879) - Removed Google
Groups e-mail from pip packaging metadata. Users browsing PYPI will have
to visit our website to find out how to reach us (we are using Discourse
and it does not offer an e-mail address).

[#3859](https://github.com/cylc/cylc-flow/pull/3859) - Fixes the query of
broadcast states to retrieve only the data for the requested ID, instead
of returning all the broadcast states in the database.

[#3815](https://github.com/cylc/cylc-flow/pull/3815) - Fixes a minor bug in the
auto-restart functionality which caused suites to wait for local jobs running
on *any* host to complete before restarting.

[#3732](https://github.com/cylc/cylc-flow/pull/3732) - XTrigger labels
are now validated to ensure that runtime errors can not occur when
exporting environment variables.

[#3632](https://github.com/cylc/cylc-flow/pull/3632) - Fix a bug that was causing
`UTC mode` specified in global config to be pretty much ignored.

[#3614](https://github.com/cylc/cylc-flow/pull/3614) - Ensure the suite always
restarts using the same time zone as the last `cylc run`.

[#3788](https://github.com/cylc/cylc-flow/pull/3788),
[#3820](https://github.com/cylc/cylc-flow/pull/3820) - Task messages and
task outputs/message triggers are now validated.

[#3614](https://github.com/cylc/cylc-flow/pull/3795) - Fix error when running
`cylc ping --verbose $SUITE`.

[#3852](https://github.com/cylc/cylc-flow/pull/3852) - Prevents registering a
workflow in a sub-directory of a run directory (as `cylc scan` would not be
able to find it).

[#3452](https://github.com/cylc/cylc-flow/pull/3452) - Fix param graph
issue when mixing offset and conditional (e.g. foo<m-1> & baz => foo<m>).

[#3982](https://github.com/cylc/cylc-flow/pull/3982) - Fix bug preventing
workflow from shutting down properly on a keyboard interrupt (Ctrl+C) in
Python 3.8+.

[#4011](https://github.com/cylc/cylc-flow/pull/4011) - Fix bug where including
a trailing slash in the suite/workflow name would cause `cylc stop`
(and possibly other commands) to silently fail.

[#4046](https://github.com/cylc/cylc-flow/pull/4046) - Fix bug where a workflow
database could still be active for a short time after the workflow stops.

-------------------------------------------------------------------------------
## __cylc-8.0a2 (2020-07-03)__

Third alpha release of Cylc 8.

(See note on cylc-8 backward-incompatible changes, above)

The commands `cylc submit` and `cylc jobscript` have been removed.

### Enhancements

[#3389](https://github.com/cylc/cylc-flow/pull/3389) - Publisher/Subscriber
network components added (0MQ PUB/SUB pattern). Used to publish fine-grained
data-store updates for the purposes of UI Server data sync, this change also
includes CLI utility: `cylc subscribe`.

[#3402](https://github.com/cylc/cylc-flow/pull/3402) - removed automatic task
job status message retries (problems that prevent message transmission are
almost never transient, and in practice job polling is the only way to
recover).

[#3463](https://github.com/cylc/cylc-flow/pull/3463) - cylc tui:
A new terminal user interface to replace the old `cylc monitor`.
An interactive collapsible tree to match the new web interface.

[#3559](https://github.com/cylc/cylc-flow/pull/3559) - Cylc configuration
files are now auto-documented from their definitions.

[#3617](https://github.com/cylc/cylc-flow/pull/3617) - For integer cycling mode
there is now a default initial cycle point of 1.

[#3423](https://github.com/cylc/cylc-flow/pull/3423) - automatic task retries
re-implemented using xtriggers. Retrying tasks will now be in the "waiting"
state with a wall_clock xtrigger set for the retry time.

### Fixes

[#3618](https://github.com/cylc/cylc-flow/pull/3618) - Clear queue configuration
warnings for referencing undefined or unused tasks.

[#3596](https://github.com/cylc/cylc-flow/pull/3596) - Fix a bug that could
prevent housekeeping of the task_action_timers DB table and cause many warnings
at restart.

[#3602](https://github.com/cylc/cylc-flow/pull/3602) - Fix a bug that prevented
cycle point format conversion by the `cylc suite-state` command and the
`suite_state` xtrigger function, if the target suite used the default format
but downstream command or suite did not.

[#3541](https://github.com/cylc/cylc-flow/pull/3541) - Don't warn that a task
was already added to an internal queue, if the queue is the same.

[#3409](https://github.com/cylc/cylc-flow/pull/3409) - prevent cylc-run from
creating directories when executed for suites that do not exist.

[#3433](https://github.com/cylc/cylc-flow/pull/3433) - fix server abort at
shutdown during remote run dir tidy (introduced during Cylc 8 development).

[#3493](https://github.com/cylc/cylc-flow/pull/3493) - Update jinja2 and
pyzmq, as well as some test/dev dependencies. Fixes Jinja2 error where
validation shows incorrect context.

[#3531](https://github.com/cylc/cylc-flow/pull/3531) - Fix job submission to
SLURM when task name has a percent `%` character.

[#3543](https://github.com/cylc/cylc-flow/pull/3543) - fixed pipe polling
issue observed on darwin (BSD) which could cause Cylc to hang.

-------------------------------------------------------------------------------
## __cylc-8.0a1 (2019-09-18)__

Second alpha release of Cylc 8.

(See note on cylc-8 backward-incompatible changes, above)

### Enhancements

[#3377](https://github.com/cylc/cylc-flow/pull/3377) - removed support for
sourcing `job-init-env.sh` in task job scripts. Use bash login scripts instead.

[#3302](https://github.com/cylc/cylc-flow/pull/3302) - improve CLI
task-globbing help.

[#2935](https://github.com/cylc/cylc-flow/pull/2935) - support alternate run
directories, particularly for sub-suites.

[#3096](https://github.com/cylc/cylc-flow/pull/3096) - add colour to the
Cylc CLI.

[#2963](https://github.com/cylc/cylc-flow/pull/2963) - make suite context
available before config parsing.

[#3274](https://github.com/cylc/cylc-flow/pull/3274) - disallow the use of
special characters in suite names.

[#3001](https://github.com/cylc/cylc-flow/pull/3001) - simplify cylc version,
dropping VERSION file and git info.

[#3007](https://github.com/cylc/cylc-flow/pull/3007) - add tests for quoting
of tilde expressions in environment section.

[#3006](https://github.com/cylc/cylc-flow/pull/3006) - remove cylc.profiling
package and cylc-profile-battery.

[#2998](https://github.com/cylc/cylc-flow/pull/2998) - Bandit security
recommendations for Cylc 8 target.

[#3024](https://github.com/cylc/cylc-flow/pull/3024) - remove remaining Cylc
Review files.

[#3022](https://github.com/cylc/cylc-flow/pull/3022) - removed LaTeX support
from check-software.

[#3029](https://github.com/cylc/cylc-flow/pull/3029) - remove dev-suites
from tests.

[#3036](https://github.com/cylc/cylc-flow/pull/3036) - re-enable EmPy
templating.

[#3044](https://github.com/cylc/cylc-flow/pull/3044) - remove GTK labels
from task states.

[#3055](https://github.com/cylc/cylc-flow/pull/3055) - simplify regexes.

[#2995](https://github.com/cylc/cylc-flow/pull/2995) - elegantly handle
known errors.

[#3069](https://github.com/cylc/cylc-flow/pull/3069) - make Python 3.7 the
min version for Cylc.

[#3068](https://github.com/cylc/cylc-flow/pull/3068) - add shellcheck to
lint shell script files.

[#3088](https://github.com/cylc/cylc-flow/pull/3088) - remove obsolete
ksh support.

[#3091](https://github.com/cylc/cylc-flow/pull/3091) - remove useless
license commands.

[#3095](https://github.com/cylc/cylc-flow/pull/3095) - run prove with
--timer.

[#3093](https://github.com/cylc/cylc-flow/pull/3093) - job.sh: run
as bash only.

[#3101](https://github.com/cylc/cylc-flow/pull/3101) - add kill all to
functional tests.

[#3123](https://github.com/cylc/cylc-flow/pull/3123) - remove Kafka
xtrigger example.

[#2990](https://github.com/cylc/cylc-flow/pull/2990) - make cylc a module.

[#3131](https://github.com/cylc/cylc-flow/pull/3131) - renamed cylc to
cylc-flow, and simplified project summary.

[#3140](https://github.com/cylc/cylc-flow/pull/3140) - cylc-flow rename in
README badges, setup.py, and a few more places.

[#3138](https://github.com/cylc/cylc-flow/pull/3138) - add suite aborted
event.

[#3132](https://github.com/cylc/cylc-flow/pull/3132) - move parsec to
cylc.parsec.

[#3113](https://github.com/cylc/cylc-flow/pull/3113) - document
select_autoescape security ignore.

[#3083](https://github.com/cylc/cylc-flow/pull/3083) - extend
ZMQClient and update docstrings.

[#3155](https://github.com/cylc/cylc-flow/pull/3155) - remove changed
variable in async_map.

[#3135](https://github.com/cylc/cylc-flow/pull/3135) - incorporate
jinja2filters into cylc.flow.jinja.filters, and use native namespaces.

[#3134](https://github.com/cylc/cylc-flow/pull/3134) - update how
CYLC_DIR is used in Cylc.

[#3165](https://github.com/cylc/cylc-flow/pull/3165) - added GitHub
Issue and Pull Request templates.

[#3272](https://github.com/cylc/cylc-flow/pull/3272),
[#3191](https://github.com/cylc/cylc-flow/pull/3191) - uniform configuration
section level for defining non-cycling and cycling graphs. E.g.:

```
# Deprecated Syntax
[scheduling]
    initial cycle point = next(T00)
    [[dependencies]]
        [[[P1D]]]
            graph = task1 => task2
```

Can now be written as:

```
# New Syntax
[scheduling]
    initial cycle point = next(T00)
    [[graph]]
        P1D = task1 => task2
```

[#3249](https://github.com/cylc/cylc-flow/pull/3249) - export the environment
variable `ISODATETIMEREF` (reference time for the `isodatetime` command from
[metomi-isodatetime](https://github.com/metomi/isodatetime/)) in task jobs to
have the same value as `CYLC_TASK_CYCLE_POINT`.

[#3286](https://github.com/cylc/cylc-flow/pull/3286) -
Removed the `cylc check-triggering` command.
Changed the `suite.rc` schema:
* Removed `[cylc]log resolved dependencies`
* Removed `[cylc][[reference test]]*` except `expected task failures`.
* Moved `[cylc]abort if any task fails` to
  `[cylc][[events]]abort if any task fails` so it lives with the other
  `abort if/on ...` settings.

[#3351](https://github.com/cylc/cylc-flow/pull/3351) - sped up suite validation
(which also affects responsiveness of suite controllers during suite startup,
restarts, and reloads).  Impact of the speedup is most noticeable when dealing
with suite configurations that contain tasks with many task outputs.

[#3358](https://github.com/cylc/cylc-flow/pull/3358) - on submitting jobs to
SLURM or LSF, the job names will now follow the pattern `task.cycle.suite`
(instead of `suite.task.cycle`), for consistency with jobs on PBS.

[#3356](https://github.com/cylc/cylc-flow/pull/3356) - default job name length
maximum for PBS is now 236 characters (i.e. assuming PBS 13 or newer). If you
are still using PBS 12 or older, you should add a site configuration to
restrict it to 15 characters.

### Fixes

[#3308](https://github.com/cylc/cylc-flow/pull/3308) - fix a long-standing bug
causing suites to stall some time after reloading a suite definition that
removed tasks from the graph.

[#3287](https://github.com/cylc/cylc-flow/pull/3287) - fix xtrigger
cycle-sequence specificity.

[#3258](https://github.com/cylc/cylc-flow/pull/3258) - leave '%'-escaped string
templates alone in xtrigger arguments.

[#3010](https://github.com/cylc/cylc-flow/pull/3010) - fixes except KeyError
in task_job_mgr.

[#3031](https://github.com/cylc/cylc-flow/pull/3031) - convert range to list
so that we can use reduce.

[#3040](https://github.com/cylc/cylc-flow/pull/3040) - add check for zero
to xrandom.

[#3018](https://github.com/cylc/cylc-flow/pull/3018) - subprocpool: use
SpooledTemporaryFile instead of TemporaryFile.

[#3032](https://github.com/cylc/cylc-flow/pull/3032) - fix syntax for
array access in cylc check-software.

[#3035](https://github.com/cylc/cylc-flow/pull/3035) - fix scheduler#shutdown
when reference-log option is used.

[#3056](https://github.com/cylc/cylc-flow/pull/3056) - fix suite freeze on
non-existent xtrigger.

[#3060](https://github.com/cylc/cylc-flow/pull/3060) - fix bug when an
AttributeError is raised, and add unit tests for xtrigger.

[#3015](https://github.com/cylc/cylc-flow/pull/3015) - use global client
zmq context.

[#3092](https://github.com/cylc/cylc-flow/pull/3092) - fix recent
shellcheck-inspired quoting errors.

[#3085](https://github.com/cylc/cylc-flow/pull/3085) - fix cylc-search
for directories without suite.rc.

[#3105](https://github.com/cylc/cylc-flow/pull/3105) - fix work location
assumption in a test.

[#3112](https://github.com/cylc/cylc-flow/pull/3112) - prepend custom
Jinja2 paths.

[#3130](https://github.com/cylc/cylc-flow/pull/3130) - remove Python 2
compatibility in setup.py for wheel.

[#3137](https://github.com/cylc/cylc-flow/pull/3137) - fix job kill
hold-retry logic.

[#3077](https://github.com/cylc/cylc-flow/pull/3077) - support single
port configuration for zmq.

[#3153](https://github.com/cylc/cylc-flow/pull/3153) - fix bug in
async_map.

[#3164](https://github.com/cylc/cylc-flow/pull/3164) - fix pclient
undefined error.

[#3173](https://github.com/cylc/cylc-flow/issues/3173) - NameError when
invalid cylc command is used (instead of a ValueError).

[#3003](https://github.com/cylc/cylc-flow/pull/3003) - Fix inheritance
with quotes using shlex.

[#3184](https://github.com/cylc/cylc-flow/pull/3184) - Fix restart
correctness when the suite has a hold point, stop point, a stop task, a stop
clock time and/or an auto stop option. These settings are now stored in the
suite run SQLite file and are retrieved on suite restart. In addition, the
settings are removed when they are consumed, e.g. if the suite stopped
previously on reaching the stop point, the stop point would be consumed, so
that on restart the suite would not stop again immediately.

The `cylc run` command can now accept `--initial-cycle-point=CYCLE-POINT`
(`--icp=CYCLE-POINT)` and `--start-cycle-point=CYCLE-POINT` options. This
change should allow the command to have  a more uniform interface with commands
such as `cylc validate`, and with the final/stop cycle point options).

After this change:
* `cylc run SUITE POINT` is equivalent to `cylc run --icp=POINT SUITE`.
* `cylc run -w SUITE POINT` is equivalent to
  `cylc run -w --start-point=POINT SUITE`.

The `cylc run` and `cylc restart` commands can now accept the
`--final-cycle-point=POINT` and `--stop-cycle-point=POINT` options. The
`--until=POINT` option is now an alias for `--final-cycle-point=POINT` option.

The `cylc run` and `cylc restart` commands can now accept the new
`--auto-shutdown` option. This option overrides the equivalent suite
configuration to force auto shutdown to be enabled. Previously, it is only
possible to disable auto shutdown on the command line.

[#3236](https://github.com/cylc/cylc-flow/pull/3236) - Fix submit number
increment logic on insert of family with tasks that were previously submitted.

[#3276](https://github.com/cylc/cylc-flow/pull/3276) - Fix log & DB recording
of broadcasts from xtriggers so they register all settings, not just one.

[#3325](https://github.com/cylc/cylc-flow/pull/3325) - Fix task event handler
*start_time* being unavailable in *started* events.

### Documentation

[#3181](https://github.com/cylc/cylc-flow/pull/3181) - moved documentation to
the new cylc/cylc-doc repository.

[#3025](https://github.com/cylc/cylc-flow/pull/3025) - fix dev-suites
reference in docs (now in examples).

[#3004](https://github.com/cylc/cylc-flow/pull/3004) - document suite
runtime interface.

[#3066](https://github.com/cylc/cylc-flow/pull/3066) - minor fix to
docs about exit-script.

[#3108](https://github.com/cylc/cylc-flow/pull/3108) - anatomy of a
job script.

[#3129](https://github.com/cylc/cylc-flow/pull/3129) - added
SECURITY.md.

[#3151](https://github.com/cylc/cylc-flow/pull/3151) - fix documentation
heading levels.

[#3158](https://github.com/cylc/cylc-flow/pull/3158) - fix \ in doco
when wrapped in ``..``.

### Security issues

None. Note that we added a `SECURITY.md` file in this release (see #3129)
with instructions for reporting security issues, as well as a
listing with current incident reports.

-------------------------------------------------------------------------------
## __cylc-8.0a0 (2019-03-12)__

First alpha release of Cylc 8. Also first release of Cylc uploaded
to PYPI: https://pypi.org/project/cylc-flow/.

(See note on cylc-8 backward-incompatible changes, above)

### Enhancements

[#2936](https://github.com/cylc/cylc-flow/pull/2936) - remove obsolete commands,
modules, configuration, and documentation.

[#2966](https://github.com/cylc/cylc-flow/pull/2966) - port Cylc to Python 3.

### Fixes

None.

### Documentation

[#2939](https://github.com/cylc/cylc-flow/pull/2939) - use higher contrast link
colours for the generated documentation.

[#2954](https://github.com/cylc/cylc-flow/pull/2954) - fix jinja2 variable
setting example suites.

[#2951](https://github.com/cylc/cylc-flow/pull/2951) - amend makefile command
and address warning.

[#2971](https://github.com/cylc/cylc-flow/pull/2971) - general single- and
multi-page User Guides.

### Security issues

None.

-------------------------------------------------------------------------------

**For changes prior to Cylc 8, see https://github.com/cylc/cylc-flow/blob/7.8.x/CHANGES.md**
