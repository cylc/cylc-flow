# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Functionality for workflow removal."""

import glob
import os
import sqlite3
from collections import deque
from contextlib import suppress
from functools import partial
from pathlib import Path
from random import shuffle
from subprocess import (
    DEVNULL,
    PIPE,
    Popen,
)
from time import sleep
from typing import (
    TYPE_CHECKING,
    Any,
    Container,
    Deque,
    Dict,
    Iterable,
    List,
    NamedTuple,
    Optional,
    Set,
    Union,
)

from cylc.flow import LOG
from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.exceptions import (
    ContactFileExists,
    CylcError,
    InputError,
    PlatformError,
    PlatformLookupError,
    ServiceFileError,
)
from cylc.flow.pathutil import (
    get_workflow_run_dir,
    parse_rm_dirs,
    remove_dir_and_target,
    remove_dir_or_file,
    remove_empty_parents,
)
from cylc.flow.platforms import (
    get_host_from_platform,
    get_install_target_to_platforms_map,
    get_localhost_install_target,
)
from cylc.flow.remote import construct_ssh_cmd
from cylc.flow.rundb import CylcWorkflowDAO
from cylc.flow.workflow_files import (
    WorkflowFiles,
    detect_old_contact_file,
    get_symlink_dirs,
    get_workflow_srv_dir,
    infer_latest_run,
    validate_workflow_name,
)

if TYPE_CHECKING:
    from optparse import Values


class RemoteCleanQueueTuple(NamedTuple):
    proc: 'Popen[str]'
    install_target: str
    platforms: List[Dict[str, Any]]


async def get_contained_workflows(partial_id) -> List[str]:
    """Return the sorted names of any workflows in a directory.

    Args:
        path: Absolute path to the dir.
        scan_depth: How many levels deep to look inside the dir.
    """
    from cylc.flow.network.scan import scan
    run_dir = Path(get_workflow_run_dir(partial_id))
    # Note: increased scan depth for safety
    scan_depth = glbl_cfg().get(['install', 'max depth']) + 1
    return sorted(
        [i['name'] async for i in scan(scan_dir=run_dir, max_depth=scan_depth)]
    )


def _clean_check(opts: 'Values', reg: str, run_dir: Path) -> None:
    """Check whether a workflow can be cleaned.

    Args:
        reg: Workflow name.
        run_dir: Path to the workflow run dir on the filesystem.
    """
    validate_workflow_name(reg)
    reg = os.path.normpath(reg)
    # Thing to clean must be a dir or broken symlink:
    if not run_dir.is_dir() and not run_dir.is_symlink():
        raise FileNotFoundError(f"No directory to clean at {run_dir}")
    db_path = (
        run_dir / WorkflowFiles.Service.DIRNAME / WorkflowFiles.Service.DB
    )
    if opts.local_only and not db_path.is_file():
        # Will reach here if this is cylc clean re-invoked on remote host
        # (workflow DB only exists on scheduler host); don't need to worry
        # about contact file.
        return
    try:
        detect_old_contact_file(reg)
    except ContactFileExists as exc:
        raise ServiceFileError(
            f"Cannot clean running workflow {reg}.\n\n{exc}"
        )


def init_clean(id_: str, opts: 'Values') -> None:
    """Initiate the process of removing a stopped workflow from the local
    scheduler filesystem and remote hosts.

    Args:
        id_: Workflow ID.
        opts: CLI options object for cylc clean.

    """
    local_run_dir = Path(get_workflow_run_dir(id_))
    with suppress(InputError):
        local_run_dir, id_ = infer_latest_run(
            local_run_dir, implicit_runN=False, warn_runN=False
        )
    try:
        _clean_check(opts, id_, local_run_dir)
    except FileNotFoundError as exc:
        LOG.info(exc)
        return

    # Parse --rm option to make sure it's valid
    rm_dirs = parse_rm_dirs(opts.rm_dirs) if opts.rm_dirs else None

    if not opts.local_only:
        platform_names = None
        db_file = Path(get_workflow_srv_dir(id_), 'db')
        if not db_file.is_file():
            # no DB -> do nothing
            if opts.remote_only:
                raise ServiceFileError(
                    f"No workflow database for {id_} - cannot perform "
                    "remote clean"
                )
            LOG.info(
                f"No workflow database for {id_} - will only clean locally"
            )
        else:
            # DB present -> load platforms
            try:
                platform_names = get_platforms_from_db(local_run_dir)
            except ServiceFileError as exc:
                raise ServiceFileError(f"Cannot clean {id_} - {exc}")
            except sqlite3.OperationalError as exc:
                # something went wrong with the query
                # e.g. the table/field we need isn't there
                LOG.warning(
                    'This database is either corrupted or not compatible with'
                    ' this version of "cylc clean".'
                    '\nTry using the version of Cylc the workflow was last ran'
                    ' with to remove it.'
                    '\nOtherwise please delete the database file.'
                )
                raise ServiceFileError(f"Cannot clean {id_} - {exc}")

        if platform_names and platform_names != {'localhost'}:
            remote_clean(
                id_, platform_names, opts.rm_dirs, opts.remote_timeout
            )

    if not opts.remote_only:
        # Must be after remote clean
        clean(id_, local_run_dir, rm_dirs)


def clean(id_: str, run_dir: Path, rm_dirs: Optional[Set[str]] = None) -> None:
    """Remove a stopped workflow from the local filesystem only.

    Deletes the workflow run directory and any symlink dirs, or just the
    specified sub dirs if rm_dirs is specified.

    Note: if the run dir has already been manually deleted, it will not be
    possible to clean any symlink dirs.

    Args:
        id_: Workflow ID.
        run_dir: Absolute path of the workflow's run dir.
        rm_dirs: Set of sub dirs to remove instead of the whole run dir.

    """
    symlink_dirs = get_symlink_dirs(id_, run_dir)
    if rm_dirs is not None:
        # Targeted clean
        for pattern in rm_dirs:
            _clean_using_glob(run_dir, pattern, symlink_dirs)
    else:
        # Wholesale clean
        LOG.debug(f"Cleaning {run_dir}")
        for symlink in symlink_dirs:
            # Remove <symlink_dir>/cylc-run/<id>/<symlink>
            remove_dir_and_target(run_dir / symlink)
        if '' not in symlink_dirs:
            # if run dir isn't a symlink dir and hasn't been deleted yet
            remove_dir_and_target(run_dir)

    # Tidy up if necessary
    # Remove `runN` symlink if it's now broken
    runN = run_dir.parent / WorkflowFiles.RUN_N
    if (
        runN.is_symlink() and
        not run_dir.exists() and
        os.readlink(str(runN)) == run_dir.name
    ):
        runN.unlink()
    # Remove _cylc-install if it's the only thing left
    cylc_install_dir = run_dir.parent / WorkflowFiles.Install.DIRNAME
    for entry in run_dir.parent.iterdir():
        if entry == cylc_install_dir:
            continue
        break
    else:  # no break
        if cylc_install_dir.is_dir():
            remove_dir_or_file(cylc_install_dir)
    # Remove any empty parents of run dir up to ~/cylc-run/
    remove_empty_parents(run_dir, id_)
    for symlink, target in symlink_dirs.items():
        # Remove empty parents of symlink target up to <symlink_dir>/cylc-run/
        remove_empty_parents(target, Path(id_, symlink))


def glob_in_run_dir(
    run_dir: Union[Path, str], pattern: str, symlink_dirs: Container[Path]
) -> List[Path]:
    """Execute a (recursive) glob search in the given run directory.

    Returns list of any absolute paths that match the pattern. However:
    * Does not follow symlinks (apart from the spcedified symlink dirs).
    * Also does not return matching subpaths of matching directories (because
        that would be redundant).

    Args:
        run_dir: Absolute path of the workflow run dir.
        pattern: The glob pattern.
        symlink_dirs: Absolute paths to the workflow's symlink dirs.
    """
    # Note: use os.path.join, not pathlib, to preserve trailing slash if
    # present in pattern
    pattern = os.path.join(glob.escape(str(run_dir)), pattern)
    # Note: don't use pathlib.Path.glob() because when you give it an exact
    # filename instead of pattern, it doesn't return broken symlinks
    matches = sorted(Path(i) for i in glob.iglob(pattern, recursive=True))
    # sort guarantees parents come before their children
    if len(matches) == 1 and not os.path.lexists(matches[0]):
        # https://bugs.python.org/issue35201
        return []
    results: List[Path] = []
    subpath_excludes: Set[Path] = set()
    for path in matches:
        for rel_ancestor in reversed(path.relative_to(run_dir).parents):
            ancestor = run_dir / rel_ancestor
            if ancestor in subpath_excludes:
                break
            if ancestor.is_symlink() and ancestor not in symlink_dirs:
                # Do not follow non-standard symlinks
                subpath_excludes.add(ancestor)
                break
            if not symlink_dirs and (ancestor in results):
                # We can be sure all subpaths of this ancestor are redundant
                subpath_excludes.add(ancestor)
                break
            if ancestor == path.parent:  # noqa: SIM102
                # Final iteration over ancestors
                if ancestor in matches and path not in symlink_dirs:
                    # Redundant (but don't exclude subpaths in case any of the
                    # subpaths are std symlink dirs)
                    break
        else:  # No break
            results.append(path)
    return results


def _clean_using_glob(
    run_dir: Path, pattern: str, symlink_dirs: Iterable[str]
) -> None:
    """Delete the files/dirs in the run dir that match the pattern.

    Does not follow symlinks (apart from the standard symlink dirs).

    Args:
        run_dir: Absolute path of workflow run dir.
        pattern: The glob pattern.
        symlink_dirs: Paths of the workflow's symlink dirs relative to
            the run dir.
    """
    abs_symlink_dirs = tuple(sorted(
        (run_dir / d for d in symlink_dirs),
        reverse=True  # ordered by deepest to shallowest
    ))
    matches = glob_in_run_dir(run_dir, pattern, abs_symlink_dirs)
    if not matches:
        LOG.info(f"No files matching '{pattern}' in {run_dir}")
        return
    # First clean any matching symlink dirs
    for path in abs_symlink_dirs:
        if path in matches:
            remove_dir_and_target(path)
            if path == run_dir:
                # We have deleted the run dir
                return
            matches.remove(path)
    # Now clean the rest
    for path in matches:
        remove_dir_or_file(path)


def remote_clean(
    reg: str,
    platform_names: Iterable[str],
    rm_dirs: Optional[List[str]] = None,
    timeout: str = '120'
) -> None:
    """Run subprocesses to clean workflows on remote install targets
    (skip localhost), given a set of platform names to look up.

    Args:
        reg: Workflow name.
        platform_names: List of platform names to look up in the global
            config, in order to determine the install targets to clean on.
        rm_dirs: Sub dirs to remove instead of the whole run dir.
        timeout: Number of seconds to wait before cancelling.
    """
    try:
        install_targets_map = (
            get_install_target_to_platforms_map(platform_names))
    except PlatformLookupError as exc:
        raise PlatformLookupError(
            f"Cannot clean {reg} on remote platforms as the workflow database "
            f"is out of date/inconsistent with the global config - {exc}")
    queue: Deque[RemoteCleanQueueTuple] = deque()
    remote_clean_cmd = partial(
        _remote_clean_cmd, reg=reg, rm_dirs=rm_dirs, timeout=timeout
    )
    for target, platforms in install_targets_map.items():
        if target == get_localhost_install_target():
            continue
        shuffle(platforms)
        LOG.info(
            f"Cleaning {reg} on install target: "
            f"{platforms[0]['install target']}"
        )
        # Issue ssh command:
        queue.append(
            RemoteCleanQueueTuple(
                remote_clean_cmd(platform=platforms[0]), target, platforms
            )
        )
    failed_targets: Dict[str, PlatformError] = {}
    # Handle subproc pool results almost concurrently:
    while queue:
        item = queue.popleft()
        ret_code = item.proc.poll()
        if ret_code is None:  # proc still running
            queue.append(item)
            continue
        out, err = item.proc.communicate()
        if out:
            LOG.info(f"[{item.install_target}]\n{out}")
        if ret_code:
            this_platform = item.platforms.pop(0)
            excp = PlatformError(
                PlatformError.MSG_TIDY,
                this_platform['name'],
                cmd=item.proc.args,
                ret_code=ret_code,
                out=out,
                err=err,
            )
            if ret_code == 255 and item.platforms:
                # SSH error; try again using the next platform for this
                # install target
                LOG.debug(excp)
                queue.append(
                    item._replace(
                        proc=remote_clean_cmd(platform=item.platforms[0])
                    )
                )
            else:  # Exhausted list of platforms
                failed_targets[item.install_target] = excp
        elif err:
            # Only show stderr from remote host in debug mode if ret code 0
            # because stderr often contains useless stuff like ssh login
            # messages
            LOG.debug(f"[{item.install_target}]\n{err}")
        sleep(0.2)
    if failed_targets:
        for target, excp in failed_targets.items():
            LOG.error(
                f"Could not clean {reg} on install target: {target}\n{excp}"
            )
        raise CylcError(f"Remote clean failed for {reg}")


def _remote_clean_cmd(
    reg: str,
    platform: Dict[str, Any],
    rm_dirs: Optional[List[str]],
    timeout: str
) -> 'Popen[str]':
    """Remove a stopped workflow on a remote host.

    Call "cylc clean --local-only" over ssh and return the subprocess.

    Args:
        reg: Workflow name.
        platform: Config for the platform on which to remove the workflow.
        rm_dirs: Sub dirs to remove instead of the whole run dir.
        timeout: Number of seconds to wait before cancelling the command.

    Raises:
        NoHostsError: If the platform is not contactable.

    """
    LOG.debug(
        f"Cleaning {reg} on install target: {platform['install target']} "
        f"(using platform: {platform['name']})"
    )
    cmd = ['clean', '--local-only', reg]
    if rm_dirs is not None:
        for item in rm_dirs:
            cmd.extend(['--rm', item])
    cmd = construct_ssh_cmd(
        cmd,
        platform,
        get_host_from_platform(platform),
        timeout=timeout,
        set_verbosity=True,
    )
    LOG.debug(" ".join(cmd))
    return Popen(  # nosec
        cmd,
        stdin=DEVNULL,
        stdout=PIPE,
        stderr=PIPE,
        text=True,
    )
    # * command constructed by internal interface


def get_platforms_from_db(run_dir: Path) -> Set[str]:
    """Return the set of names of platforms (that jobs ran on) from the DB.

    Warning:
        This does NOT upgrade the workflow database!

        We could upgrade the DB for backward compatiblity, but we haven't
        got any upgraders for this table yet so there's no point.

        Note that upgrading the DB here would not help with forward
        compatibility. We can't apply upgraders which don't exist yet.

    Args:
        run_dir: The workflow run directory.

    Raises:
        sqlite3.OperationalError: in the event the table/field required for
        cleaning is not present.

    """
    with CylcWorkflowDAO(
        run_dir / WorkflowFiles.Service.DIRNAME / WorkflowFiles.Service.DB
    ) as pri_dao:
        platform_names = pri_dao.select_task_job_platforms()

    return platform_names
