#!/usr/bin/env python3

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

"""cylc cat-log [OPTIONS] ARGS

View Cylc workflow and job log files.

Print, tail-follow, print path, or list directory, of local or remote job
and scheduler logs. Job runner view commands (e.g. 'qcat') are used if defined
in global config and the job is running.

For standard log types use the short-cut option argument or full filename (e.g.
for job stdout "-f o" or "-f job.out" will do).

To list the local job log directory of a remote task, choose "-m l" (directory
list mode) and a local file, e.g. "-f a" (job-activity.log).

If remote job logs are retrieved to the workflow host on completion (global
config '[JOB-HOST]retrieve job logs = True') and the job is not currently
running, the local (retrieved) log will be accessed unless '-o/--force-remote'
is used.

The correct cycle point format of the workflow must be used for job logs,
but can be discovered with '--mode=d' (print-dir).

Examples:
  # for a task "2020/bar" in workflow "foo"

  # Print workflow log:
  $ cylc cat-log foo

  # Print specific workflow log:
  $ cylc cat-log foo -f 02-start-01.log

  # Print task stdout:
  $ cylc cat-log foo//2020/bar
  $ cylc cat-log -f o foo//2020/bar

  # Print task stderr:
  $ cylc cat-log -f e foo//2020/bar
"""

import os
from contextlib import suppress
from glob import glob
from pathlib import Path
import shlex
from subprocess import Popen, PIPE, DEVNULL
import sys
from typing import TYPE_CHECKING

from cylc.flow.exceptions import InputError
import cylc.flow.flags
from cylc.flow.hostuserutil import is_remote_platform
from cylc.flow.id_cli import parse_id
from cylc.flow.loggingutil import LOG_FILE_EXTENSION
from cylc.flow.option_parsers import (
    ID_MULTI_ARG_DOC,
    CylcOptionParser as COP,
    verbosity_to_opts,
)
from cylc.flow.pathutil import (
    expand_path,
    get_remote_workflow_run_job_dir,
    get_workflow_run_job_dir,
    get_workflow_run_pub_db_path,
    get_workflow_run_scheduler_log_dir,
    get_workflow_run_scheduler_log_path)
from cylc.flow.remote import remote_cylc_cmd, watch_and_kill
from cylc.flow.rundb import CylcWorkflowDAO
from cylc.flow.task_job_logs import (
    JOB_LOG_OUT, JOB_LOG_ERR, JOB_LOG_OPTS, NN, JOB_LOG_ACTIVITY)
from cylc.flow.terminal import cli_function
from cylc.flow.platforms import get_platform


if TYPE_CHECKING:
    from optparse import Values


# Immortal tail-follow processes on job hosts can be cleaned up by killing
# my subprocesses if my PPID or PPPID changes (due to parent ssh connection
# dying). This works even if the sshd-invoked
# "$(SHELL) -c <remote-command>" does not
# exec <remote-command> (affects whether my parent process or I get inherited
# by init).
#
# Example: On host A: cylc cat-log --host=B <workflow> <task-on-C>
#    => on host A: cat-log spawns subprocess
#                     ssh B "cylc cat-log <workflow> <task-on-C>"
#      => on host B: cat-log spawns subprocess
#                     ssh C "cylc cat-log --remote <workflow> <task-on-C>"
#        => on host C: cat-log spawns subprocess
#                       tail -f <task-on-C>.out
#
# Then Ctrl-C (or exit log viewer) on host-A:
#    => ssh from A to B dies
#       => on B: cat-log detects the previous,
#                  and kills its ssh subprocess to C
#         => on C: cat-log detects the previous,
#                  and kills its tail subprocess, then exits as finished


MODES = {
    'p': 'print',
    'l': 'list-dir',
    'd': 'print-dir',
    'c': 'cat',
    't': 'tail',
}


BUFSIZE = 1024 * 1024


def colorise_cat_log(cat_proc, color=False, stdout=None):
    """Print a Cylc log file in color at it would appear in the terminal.

    Args:
        cat_proc (subprocess.Process):
            A process which outputs a Cylc log file i.e. `cat`.
        color (bool):
            If `True` log will appear in color, if `False` no control
            characters will be added.
        stdout:
            Set the stdout argument of "Popen" if "color=True".

    """
    if color:
        color_proc = Popen(  # nosec
            [
                sys.executable, '-c',
                '; '.join([
                    'import sys',
                    'from cylc.flow.loggingutil import re_formatter',
                    'print(re_formatter(sys.stdin.read()), end="")'
                ]),
                # * there is no untrusted input, everything is hardcoded
            ],
            stdin=PIPE,
            stdout=stdout,
        )
        return color_proc.communicate(cat_proc.communicate()[0])
    else:
        cat_proc.wait()


def view_log(logpath, mode, tailer_tmpl, batchview_cmd=None, remote=False,
             color=False):
    """View (by mode) local log file. This is only called on the file host.

    batchview_cmd is a job-runner-specific job stdout or stderr cat or tail
    command (e.g. 'qcat') that may be implemented for job runners that don't
    write logs to their final locations until after the job completes.

    If remote is True, we are executing on a remote host for a log file there.

    """
    # The log file path may contain '$USER' to be evaluated on the job host.
    if mode == 'print':
        # Print location even if the workflow does not exist yet.
        print(logpath)
        return 0
    elif not os.path.exists(logpath) and batchview_cmd is None:
        # Note: batchview_cmd may not need to have access to logpath, so don't
        # test for existence of path if it is set.
        sys.stderr.write('file not found: %s\n' % logpath)
        return 1
    elif mode == 'print-dir':
        print(os.path.dirname(logpath))
        return 0
    elif mode == 'list-dir':
        for entry in sorted(os.listdir(os.path.dirname(logpath))):
            print(entry)
        return 0
    elif mode == 'cat':
        # print file contents to stdout.
        if batchview_cmd is not None:
            cmd = shlex.split(batchview_cmd)
        else:
            cmd = ['cat', logpath]
        proc1 = Popen(  # nosec
            cmd,
            stdin=DEVNULL,
            stdout=PIPE if color else None
        )
        # * batchview command is user configurable
        colorise_cat_log(proc1, color=color)
        return 0
    elif mode == 'tail':
        if batchview_cmd is not None:
            cmd = batchview_cmd
        else:
            cmd = tailer_tmpl % {"filename": logpath}
        proc = Popen(shlex.split(cmd), stdin=DEVNULL)  # nosec
        # * batchview command is user configurable
        with suppress(KeyboardInterrupt):
            watch_and_kill(proc)
        return proc.wait()


def get_option_parser() -> COP:
    """Set up the CLI option parser."""
    parser = COP(
        __doc__,
        argdoc=[
            ID_MULTI_ARG_DOC,
        ]
    )

    parser.add_option(
        "-f", "--file",
        help="  Job log: %s; default o(out)." % (
             ', '.join(['%s(%s)' % (i, j)
                       for i, j in JOB_LOG_OPTS.items()])) +
             "  Or <filename> for custom (and standard) job logs.",
        metavar="LOG", action="store", default=None, dest="filename")

    parser.add_option(
        "-m", "--mode",
        help="Mode: %s. Default c(cat)." % (
            ', '.join(['%s(%s)' % (i, j) for i, j in MODES.items()])),
        action="store", choices=list(MODES.keys()) + list(MODES.values()),
        default='c', dest="mode")

    parser.add_option(
        "-r", "--rotation",
        help="Workflow log integer rotation number. 0 for current, 1 for "
        "next oldest, etc.",
        metavar="INT", action="store", dest="rotation_num")

    parser.add_option(
        "-o", "--force-remote",
        help="View remote logs remotely even if they have been retrieved"
        " to the workflow host (default False).",
        action="store_true", default=False, dest="force_remote")

    parser.add_option(
        "-s", "--submit-number", "-t", "--try-number",
        help="Job submit number (default=%s, i.e. latest)." % NN,
        metavar="INT", action="store", dest="submit_num", default=NN)

    parser.add_option(
        "--remote-arg",
        help="(for internal use: continue processing on job host)",
        action="append", dest="remote_args")

    return parser


def get_task_job_attrs(workflow_id, point, task, submit_num):
    """Return job (platform, job_runner_name, live_job_id).

    live_job_id is the job ID if job is running, else None.

    """
    with CylcWorkflowDAO(
        get_workflow_run_pub_db_path(workflow_id), is_public=True
    ) as dao:
        task_job_data = dao.select_task_job(point, task, submit_num)
    if task_job_data is None:
        return (None, None, None)
    job_runner_name = task_job_data["job_runner_name"]
    job_id = task_job_data["job_id"]
    if (not job_runner_name or not job_id
            or not task_job_data["time_run"]
            or task_job_data["time_run_exit"]):
        live_job_id = None
    else:
        live_job_id = job_id
    return (task_job_data["platform_name"], job_runner_name, live_job_id)


@cli_function(get_option_parser)
def main(
    parser: COP,
    options: 'Values',
    *ids,
    color: bool = False
) -> None:
    """Implement cylc cat-log CLI.

    Determine log path, user@host, batchview_cmd, and action (print, dir-list,
    cat, or tail), and then if the log path is:
      a) local: perform action on log path, or
      b) remote: re-invoke cylc cat-log as a) on the remote account

    """
    if options.remote_args:
        # Invoked on job hosts for job logs only, as a wrapper to view_log().
        # Tail and batchview commands from global config on workflow host).
        logpath, mode, tail_tmpl = options.remote_args[0:3]
        logpath = expand_path(logpath)
        tail_tmpl = expand_path(tail_tmpl)
        try:
            batchview_cmd = options.remote_args[3]
        except IndexError:
            batchview_cmd = None
        res = view_log(logpath, mode, tail_tmpl, batchview_cmd, remote=True,
                       color=color)
        if res == 1:
            sys.exit(res)
        return

    workflow_id, tokens, _ = parse_id(*ids, constraint='mixed')

    # Get long-format mode.
    try:
        mode = MODES[options.mode]
    except KeyError:
        mode = options.mode

    if not tokens or not tokens.get('task'):
        logpath = get_workflow_run_scheduler_log_path(workflow_id)
        if options.rotation_num:
            log_dir = Path(logpath).parent
            logs = glob(f'{log_dir}/*{LOG_FILE_EXTENSION}')
            logs.sort(key=os.path.getmtime, reverse=True)
            try:
                logpath = logs[int(options.rotation_num)]
            except IndexError:
                raise InputError(
                    "max rotation %d" % (len(logs) - 1))
        # Cat workflow logs, local only.
        if options.filename is not None and not options.rotation_num:
            logpath = os.path.join(get_workflow_run_scheduler_log_dir(
                    workflow_id)/str(options.filename))
        tail_tmpl = os.path.expandvars(
            get_platform()["tail command template"]
        )
        out = view_log(logpath, mode, tail_tmpl, color=color)
        if out == 1:
            sys.exit(1)
        return

    else:
        # Cat task job logs, may be on workflow or job host.
        if options.rotation_num is not None:
            raise InputError(
                "only workflow (not job) logs get rotated")
        task = tokens['task']
        point = tokens['cycle']
        if options.submit_num != NN:
            try:
                options.submit_num = "%02d" % int(options.submit_num)
            except ValueError:
                parser.error("Illegal submit number: %s" % options.submit_num)
        if options.filename is None:
            options.filename = JOB_LOG_OUT
        else:
            # Convert short filename args to long (e.g. 'o' to 'job.out').
            with suppress(KeyError):
                options.filename = JOB_LOG_OPTS[options.filename]
                # KeyError: Is already long form (standard log, or custom).
        platform_name, job_runner_name, live_job_id = get_task_job_attrs(
            workflow_id, point, task, options.submit_num)
        platform = get_platform(platform_name)
        batchview_cmd = None
        if live_job_id is not None:
            # Job is currently running. Get special job runner log view
            # command (e.g. qcat) if one exists, and the log is out or err.
            conf_key = None
            if options.filename == JOB_LOG_OUT:
                if mode == 'cat':
                    conf_key = "out viewer"
                elif mode == 'tail':
                    conf_key = "out tailer"
            elif options.filename == JOB_LOG_ERR:
                if mode == 'cat':
                    conf_key = "err viewer"
                elif mode == 'tail':
                    conf_key = "err tailer"
            if conf_key is not None:
                batchview_cmd_tmpl = None
                with suppress(KeyError):
                    batchview_cmd_tmpl = platform[conf_key]
                if batchview_cmd_tmpl is not None:
                    batchview_cmd = batchview_cmd_tmpl % {
                        "job_id": str(live_job_id)}

        log_is_remote = (is_remote_platform(platform)
                         and (options.filename != JOB_LOG_ACTIVITY))
        log_is_retrieved = (platform['retrieve job logs']
                            and live_job_id is None)
        if log_is_remote and (not log_is_retrieved or options.force_remote):
            logpath = os.path.normpath(get_remote_workflow_run_job_dir(
                workflow_id, point, task, options.submit_num,
                options.filename))
            tail_tmpl = platform["tail command template"]
            # Reinvoke the cat-log command on the remote account.
            cmd = ['cat-log', *verbosity_to_opts(cylc.flow.flags.verbosity)]
            for item in [logpath, mode, tail_tmpl]:
                cmd.append('--remote-arg=%s' % shlex.quote(item))
            if batchview_cmd:
                cmd.append('--remote-arg=%s' % shlex.quote(batchview_cmd))
            cmd.append(workflow_id)
            # TODO: Add Intelligent Host selection to this
            with suppress(KeyboardInterrupt):
                # (Ctrl-C while tailing)
                # NOTE: This will raise NoHostsError if the platform is not
                # contactable
                remote_cylc_cmd(
                    cmd,
                    platform,
                    capture_process=False,
                    manage=(mode == 'tail'),
                    text=False
                )
        else:
            # Local task job or local job log.
            logpath = os.path.normpath(get_workflow_run_job_dir(
                workflow_id, point, task, options.submit_num,
                options.filename))
            tail_tmpl = os.path.expandvars(platform["tail command template"])
            out = view_log(logpath, mode, tail_tmpl, batchview_cmd,
                           color=color)
            sys.exit(out)
