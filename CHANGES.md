# Changelog

List of notable changes, for a complete list of changes see the
[closed milestones](https://github.com/cylc/cylc-flow/milestones?state=closed)
for each release.

<!-- The topmost release date is automatically updated by GitHub Actions. When
creating a new release entry be sure to copy & paste the span tag with the
`actions:bind` attribute, which is used by a regex to find the text to be
updated. Only the first match gets replaced, so it's fine to leave the old
ones in. -->

## __cylc-8.2.0 (<span actions:bind='release-date'>Upcoming</span>)__

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

-[#5605](https://github.com/cylc/cylc-flow/pull/5605) - A shorthand for defining
-a list of strings - Before: `cylc command -s "X=['a', 'bc', 'd']"` - After:
-`cylc command -z X=a,bc,d`.

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

[#5525](https://github.com/cylc/cylc-flow/pull/5525) - Jobs can use scripts
in `share/bin` and Python modules in `share/lib/python`.

[#5328](https://github.com/cylc/cylc-flow/pull/5328) -
Efficiency improvements to reduce task management overheads on the Scheduler.

[#5611](https://github.com/cylc/cylc-flow/pull/5611) -
Improve the documentation of the GraphQL schema.

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

### Fixes

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
