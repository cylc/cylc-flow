# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
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

"""Record version control information on workflow install."""

from collections import OrderedDict
from pathlib import Path
from subprocess import Popen, DEVNULL, PIPE
from typing import Iterable, Optional, TYPE_CHECKING

from cylc.flow import LOG
from cylc.flow.exceptions import CylcError

if TYPE_CHECKING:
    from cylc.flow.option_parsers import Options


class VCInfo:
    """Centralised commands etc for recording version control information."""

    SVN = 'svn'
    GIT = 'git'

    INFO_COMMANDS = {
        SVN: ['info', '--non-interactive'],
        GIT: ['describe', '--always', '--dirty']
    }

    # git ['show', '--quiet', '--format=short'],

    STATUS_COMMANDS = {
        SVN: ['status', '--non-interactive'],
        GIT: ['status', '--short']
    }

    DIFF_COMMANDS = {
        SVN: ['diff', '--internal-diff', '--non-interactive'],
        GIT: ['diff', 'HEAD']
        # ['diff', '--no-index', '/dev/null', '{0}']  # untracked files
    }

    GIT_REV_PARSE_COMMAND = ['rev-parse', 'HEAD']

    NOT_REPO_ERRS = {
        SVN: ['svn: e155007:',
              'svn: warning: w155007:'],
        GIT: ['fatal: not a git repository',
              'warning: not a git repository']
    }

    SVN_INFO_KEYS = [
        'revision', 'url', 'working copy root path', 'repository uuid'
    ]


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


def get_vc_info(path: str) -> Optional['OrderedDict[str, str]']:
    """Return the version control information for a repository, given its path.
    """
    info = OrderedDict()
    for vcs, args in VCInfo.INFO_COMMANDS.items():
        try:
            out = _run_cmd(vcs, args, cwd=path)
        except VCSNotInstalledError as exc:
            LOG.debug(exc)
            continue
        except OSError as exc:
            if any(exc.strerror.lower().startswith(err)
                   for err in VCInfo.NOT_REPO_ERRS[vcs]):
                LOG.debug(f"Source dir {path} is not a {vcs} repository")
                continue
            else:
                raise exc

        info['version control system'] = vcs
        if vcs == VCInfo.SVN:
            info.update(parse_svn_info(out))
        elif vcs == VCInfo.GIT:
            info['repository version'] = out.splitlines()[0]
            info['commit'] = get_git_commit(path)
            info['working copy root path'] = path
        info['status'] = get_status(vcs, path)

        LOG.debug(f"{vcs} repository detected")
        return info

    return None


def _run_cmd(vcs: str, args: Iterable[str], cwd: str) -> str:
    """Run a command, return stdout.

    Args:
        vcs: The version control system.
        args: The args to pass to the version control command.
        cwd: Directory to run the command in.

    Raises:
        OSError: with stderr if non-zero return code.
    """
    cmd = [vcs, *args]
    try:
        proc = Popen(
            cmd, cwd=cwd, stdin=DEVNULL, stdout=PIPE, stderr=PIPE, text=True)
    except FileNotFoundError as exc:
        # This will only be raised if the VCS command is not installed,
        # otherwise Popen() will succeed with a non-zero return code
        raise VCSNotInstalledError(vcs, exc)
    ret_code = proc.wait()
    out, err = proc.communicate()
    if ret_code:
        raise OSError(ret_code, err)
    return out


def write_vc_info(info: 'OrderedDict[str, str]', run_dir: str) -> None:
    """Write version control info to the workflow's vcs log dir.

    Args:
        info: The vcs info.
        run_dir: The workflow run directory.
    """
    if not info:
        raise ValueError("Nothing to write")
    info_file = Path(run_dir, 'log', 'version', 'vcs.conf')
    info_file.parent.mkdir(exist_ok=True)
    with open(info_file, 'w') as f:
        for key, value in info.items():
            if key == 'status':
                f.write(f"{key} = \"\"\"\n")
                f.write(f"{value}\n")
                f.write("\"\"\"\n")
            else:
                f.write(f"{key} = \"{value}\"\n")


def get_git_commit(path: str) -> str:
    """Return the hash of the HEAD of the repo at path."""
    args = VCInfo.GIT_REV_PARSE_COMMAND
    return _run_cmd(VCInfo.GIT, args, cwd=path).splitlines()[0]


def get_status(vcs: str, path: str) -> str:
    """Return the short status of a repo.

    Args:
        vcs: The version control system.
        path: The path to the repository.
    """
    args = VCInfo.STATUS_COMMANDS[vcs]
    return _run_cmd(vcs, args, cwd=path).rstrip('\n')


def parse_svn_info(info_text: str) -> 'OrderedDict[str, str]':
    """Return OrderedDict of certain info parsed from svn info raw output."""
    ret = OrderedDict()
    for line in info_text.splitlines():
        if line:
            key, value = (ln.strip() for ln in line.split(':', 1))
            key = key.lower()
            if key in VCInfo.SVN_INFO_KEYS:
                ret[key] = value
    return ret


def get_diff(vcs: str, path: str) -> str:
    """Return the diff of uncommitted changes for a repository.

    Args:
        vcs: The version control system.
        path: The path to the repo.
    """
    args = VCInfo.DIFF_COMMANDS[vcs]
    diff = _run_cmd(vcs, args, cwd=path)
    header = (
        "# Auto-generated diff of uncommitted changes in the Cylc "
        "workflow repository:\n"
        f"#   {path}")
    return f"{header}\n{diff}"


def write_diff(diff: str, run_dir: str) -> None:
    """Write a diff to the workflow's vcs log dir.

    Args:
        diff: The diff.
        run_dir: The workflow run directory.
    """
    if not diff:
        raise ValueError("Nothing to write")
    diff_file = Path(run_dir, 'log', 'version', 'uncommitted.diff')
    diff_file.parent.mkdir(exist_ok=True)
    with open(diff_file, 'w') as f:
        f.write(diff)


# Entry point:
def main(dir_: str, opts: 'Options', dest_root: str) -> bool:
    """Entry point for this plugin. Write version control info and any
    uncommmited diff to the workflow log dir.

    Args:
        dir_: Workflow source dir for cylc install.
        opts: CLI options (requirement for post_install entry point, but
            not used here)
        dest_root: Workflow run dir.

    Return True if source dir is a supported repo, else False.
    """
    vc_info = get_vc_info(dir_)
    if vc_info is None:
        return False
    write_vc_info(vc_info, dest_root)
    vcs = vc_info['version control system']
    diff = get_diff(vcs, dir_)
    write_diff(diff, dest_root)
    return True
