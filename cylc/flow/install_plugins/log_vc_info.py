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

"""Record version control information to the workflow log directory on
installation.

If the workflow source directory is a supported repository/working copy
(git or svn), information about the working copy will be saved in
``<run-dir>/log/version/vcs.json``.

An example of this information for a git repo:

.. code-block:: json

   {
       "version control system": "git",
       "repository version": "2.8.0-dirty",
       "commit": "e5dc6573dd70cabd8f973d1535c17c29c026d553",
       "working copy root path": "~/cylc-src/my-workflow-git",
       "status": [
           " M flow.cylc",
           "M  bin/thing.sh"
       ]
   }

And for an svn working copy:

.. code-block:: json

   {
       "version control system": "svn",
       "working copy root path": "~/cylc-src/my-workflow-svn",
       "url": "file:///home/my-workflow-svn/trunk",
       "repository uuid": "219f5687-8eb8-44b1-beb6-e8220fa964d3",
       "revision": "14",
       "status": [
           "M       readme.txt"
       ]
   }

Any uncommitted changes will also be saved as a diff in
``<run-dir>/log/version/uncommitted.diff``.

.. note::

   Git does not include untracked files in the diff.
"""

import json
from pathlib import Path
from subprocess import Popen, DEVNULL, PIPE
from typing import (
    Any, Dict, Iterable, List, Optional, TYPE_CHECKING, TextIO, Union, overload
)

from cylc.flow import LOG
from cylc.flow.exceptions import CylcError
from cylc.flow.workflow_files import WorkflowFiles

if TYPE_CHECKING:
    from optparse import Values


SVN = 'svn'
GIT = 'git'

INFO_COMMANDS: Dict[str, List[str]] = {
    SVN: ['info', '--non-interactive'],
    GIT: ['describe', '--always', '--dirty']
}

STATUS_COMMANDS: Dict[str, List[str]] = {
    SVN: ['status', '--non-interactive'],
    GIT: ['status', '--short']
}

DIFF_COMMANDS: Dict[str, List[str]] = {
    SVN: ['diff', '--internal-diff', '--non-interactive'],
    GIT: ['diff', 'HEAD']
    # ['diff', '--no-index', '/dev/null', '{0}']  # untracked files
}

GIT_REV_PARSE_COMMAND: List[str] = ['rev-parse', 'HEAD']

NOT_REPO_ERRS: Dict[str, List[str]] = {
    SVN: ['svn: e155007:',
          'svn: warning: w155007:'],
    GIT: ['fatal: not a git repository',
          'warning: not a git repository']
}

NO_BASE_ERRS: Dict[str, List[str]] = {
    SVN: [],  # Not possible for svn working copy to have no base commit?
    GIT: ['fatal: bad revision \'head\'',
          'fatal: ambiguous argument \'head\': unknown revision']
}

SVN_INFO_KEYS: List[str] = [
    'revision', 'url', 'working copy root path', 'repository uuid'
]


LOG_VERSION_DIR = Path(WorkflowFiles.LOG_DIR, 'version')
DIFF_FILENAME = 'uncommitted.diff'
INFO_FILENAME = 'vcs.json'
JSON_INDENT = 4


class VCSNotInstalledError(CylcError):
    """Exception to be raised if an attempted VCS command is not installed.

    Args:
        vcs: The version control system command.
        exc: The exception that was raised when attempting to run the command.
    """
    def __init__(self, vcs: str, exc: Exception) -> None:
        self.vcs = vcs
        self.exc = exc

    def __str__(self) -> str:
        return f"{self.vcs} does not appear to be installed ({self.exc})"


class VCSMissingBaseError(CylcError):
    """Exception to be raised if a repository is missing a base commit.

    Args:
        vcs: The version control system command.
        repo_path: The path to the working copy.
    """
    def __init__(self, vcs: str, repo_path: Union[Path, str]) -> None:
        self.vcs = vcs
        self.path = repo_path

    def __str__(self) -> str:
        return f"{self.vcs} repository at {self.path} is missing a base commit"


def get_vc_info(path: Union[Path, str]) -> Optional[Dict[str, Any]]:
    """Return the version control information for a repository, given its path.
    """
    info: Dict[str, Any] = {}
    missing_base = False
    for vcs, args in INFO_COMMANDS.items():
        try:
            out = _run_cmd(vcs, args, cwd=path)
        except VCSNotInstalledError as exc:
            LOG.debug(exc)
            continue
        except VCSMissingBaseError as exc:
            missing_base = True
            LOG.debug(exc)
        except OSError as exc:
            if not any(
                exc.strerror.lower().startswith(err)
                for err in NOT_REPO_ERRS[vcs]
            ):
                raise exc
            else:
                LOG.debug(f"Source dir {path} is not a {vcs} repository")
                continue

        info['version control system'] = vcs
        if vcs == SVN:
            info.update(_parse_svn_info(out))
        elif vcs == GIT:
            if not missing_base:
                info['repository version'] = out.splitlines()[0]
                info['commit'] = _get_git_commit(path)
            info['working copy root path'] = str(path)
        info['status'] = get_status(vcs, path)

        LOG.debug(f"{vcs} repository detected")
        return info

    return None


@overload
def _run_cmd(
    vcs: str, args: Iterable[str], cwd: Union[Path, str], stdout: int = PIPE
) -> str:
    ...


@overload
def _run_cmd(
    vcs: str, args: Iterable[str], cwd: Union[Path, str], stdout: TextIO
) -> None:
    ...


def _run_cmd(
    vcs: str,
    args: Iterable[str],
    cwd: Union[Path, str],
    stdout: Union[TextIO, int] = PIPE
) -> Optional[str]:
    """Run a VCS command.

    Args:
        vcs: The version control system.
        args: The args to pass to the version control command.
        cwd: Directory to run the command in.
        stdout: Where to redirect output (either PIPE or a
            text stream/file object). Note: only use PIPE for
            commands that will not generate a large output, otherwise
            the pipe might get blocked.

    Returns:
        Stdout output if stdout=PIPE, else None as the output has been
        written directly to the specified file.

    Raises:
        VCSNotInstalledError: The VCS is not found.
        VCSMissingBaseError: There is no base commit in the repo.
        OSError: Non-zero return code for VCS command.
    """
    cmd = [vcs, *args]
    try:
        proc = Popen(  # nosec
            cmd,
            cwd=cwd,
            stdin=DEVNULL,
            stdout=stdout,
            stderr=PIPE,
            text=True,
        )
        # (nosec because commands are defined in constants at top of module)
    except FileNotFoundError as exc:
        # This will only be raised if the VCS command is not installed,
        # otherwise Popen() will succeed with a non-zero return code
        raise VCSNotInstalledError(vcs, exc)
    ret_code = proc.wait()
    out, err = proc.communicate()
    if ret_code:
        if any(err.lower().startswith(msg) for msg in NO_BASE_ERRS[vcs]):
            # No base commit in repo
            raise VCSMissingBaseError(vcs, cwd)
        raise OSError(ret_code, err)
    return out


def write_vc_info(
    info: Dict[str, Any], run_dir: Union[Path, str]
) -> None:
    """Write version control info to the workflow's vcs log dir.

    Args:
        info: The vcs info.
        run_dir: The workflow run directory.
    """
    if not info:
        raise ValueError("Nothing to write")
    info_file = Path(run_dir, LOG_VERSION_DIR, INFO_FILENAME)
    info_file.parent.mkdir(exist_ok=True, parents=True)
    with open(info_file, 'w') as f:
        f.write(
            json.dumps(info, indent=JSON_INDENT)
        )


def _get_git_commit(path: Union[Path, str]) -> str:
    """Return the hash of the HEAD of the repo at path."""
    args = GIT_REV_PARSE_COMMAND
    return _run_cmd(GIT, args, cwd=path).splitlines()[0]


def get_status(vcs: str, path: Union[Path, str]) -> List[str]:
    """Return the short status of a repo, as a list of lines.

    Args:
        vcs: The version control system.
        path: The path to the repository.
    """
    args = STATUS_COMMANDS[vcs]
    return _run_cmd(vcs, args, cwd=path).rstrip('\n').split('\n')


def _parse_svn_info(info_text: str) -> Dict[str, Any]:
    """Return OrderedDict of certain info parsed from svn info raw output."""
    ret: Dict[str, Any] = {}
    for line in info_text.splitlines():
        if line:
            key, value = (ln.strip() for ln in line.split(':', 1))
            key = key.lower()
            if key in SVN_INFO_KEYS:
                ret[key] = value
    return ret


def write_diff(
    vcs: str, repo_path: Union[Path, str], run_dir: Union[Path, str]
) -> Path:
    """Get and write the diff of uncommitted changes for a repository to the
    workflow's vcs log dir.

    Args:
        vcs: The version control system.
        repo_path: The path to the repo.
        run_dir: The workflow run directory.

    Returns the path to diff file.
    """
    args = DIFF_COMMANDS[vcs]
    args.append(
        str(repo_path) if Path(repo_path).is_absolute() else
        str(Path().cwd() / repo_path)
    )

    diff_file = Path(run_dir, LOG_VERSION_DIR, DIFF_FILENAME)
    diff_file.parent.mkdir(exist_ok=True)

    with open(diff_file, 'a') as f:
        f.write(
            "# Auto-generated diff of uncommitted changes in the Cylc "
            "workflow repository:\n"
            f"#   {repo_path}\n"
        )
        f.flush()
        try:
            _run_cmd(vcs, args, repo_path, stdout=f)
        except VCSMissingBaseError as exc:
            f.write(f"# No diff - {exc}")
    return diff_file


# Entry point:
def main(
    srcdir: Union[Path, str], opts: 'Values', rundir: Union[Path, str]
) -> bool:
    """Entry point for this plugin. Write version control info and any
    uncommmited diff to the workflow log dir.

    Args:
        srcdir: Workflow source dir for cylc install.
        opts: CLI options (requirement for post_install entry point, but
            not used here)
        rundir: Workflow run dir.

    Return True if source dir is a supported repo, else False.
    """
    vc_info = get_vc_info(srcdir)
    if vc_info is None:
        return False
    vcs = vc_info['version control system']
    write_vc_info(vc_info, rundir)
    write_diff(vcs, srcdir, rundir)
    return True
