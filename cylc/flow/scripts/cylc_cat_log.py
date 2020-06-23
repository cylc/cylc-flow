#!/usr/bin/env python3

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

"""cylc [info] cat-log|log [OPTIONS] ARGS

Print, view-in-editor, or tail-follow content, print path, or list directory,
of local or remote task job and suite server logs. Batch-system view commands
(e.g. 'qcat') are used if defined in global config and the job is running.

For standard log types use the short-cut option argument or full filename (e.g.
for job stdout "-f o" or "-f job.out" will do).

To list the local job log directory of a remote task, choose "-m l" (directory
list mode) and a local file, e.g. "-f a" (job-activity.log).

If remote job logs are retrieved to the suite host on completion (global config
'[JOB-HOST]retrieve job logs = True') and the job is not currently running, the
local (retrieved) log will be accessed unless '-o/--force-remote' is used.

Custom job logs (written to $CYLC_TASK_LOG_DIR on the job host) can be
listed in 'extra log files' in the suite definition. The file
name must be given, but can be discovered with '--mode=l' (list-dir).

The correct cycle poin t format of the suite must be used for task job logs,
but can be discovered with '--mode=d' (print-dir).

Basic examples, for a task "bar.2020" in suite "foo":
  Print suite log:
    cylc cat-log foo
  Print task stdout:
    cylc cat-log foo bar.2020
    cylc cat-log -f o foo bar.2020
  Print task stderr:
    cylc cat-log -f e foo bar.2020

Note the --host/user options are not needed to view remote job logs. They are
the general command reinvocation options for sites using ssh-based task
messaging."""

import sys
from cylc.flow.remote import remrun, remote_cylc_cmd, watch_and_kill

# Disallow remote re-invocation of edit mode (result: "ssh HOST vim <file>").
if remrun(abort_if='edit', forward_x11=True):
    sys.exit(0)

import os
import shlex
from contextlib import suppress
from getpass import getuser
from glob import glob
from shlex import quote
from stat import S_IRUSR
from tempfile import NamedTemporaryFile
from subprocess import Popen, PIPE

from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.exceptions import UserInputError
import cylc.flow.flags
from cylc.flow.hostuserutil import is_remote_platform
from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.pathutil import (
    get_remote_suite_run_job_dir,
    get_suite_run_job_dir,
    get_suite_run_log_name,
    get_suite_run_pub_db_name)
from cylc.flow.rundb import CylcSuiteDAO
from cylc.flow.task_id import TaskID
from cylc.flow.task_job_logs import (
    JOB_LOG_OUT, JOB_LOG_ERR, JOB_LOG_OPTS, NN, JOB_LOGS_LOCAL)
from cylc.flow.terminal import cli_function
from cylc.flow.platforms import forward_lookup, get_host_from_platform


# Immortal tail-follow processes on job hosts can be cleaned up by killing
# my subprocesses if my PPID or PPPID changes (due to parent ssh connection
# dying). This works even if cat-log is invoked with '--host' from a third
# host, and even if the sshd-invoked "$(SHELL) -c <remote-command>" does not
# exec <remote-command> (affects whether my parent process or I get inherited
# by init).
#
# Example: On host A: cylc cat-log --host=B <suite> <task-on-C>
#    => on host A: cat-log spawns subprocess
#                     ssh B "cylc cat-log <suite> <task-on-C>"
#      => on host B: cat-log spawns subprocess
#                     ssh C "cylc cat-log --remote <suite> <task-on-C>"
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
    'e': 'edit'
}


BUFSIZE = 1024 * 1024


def colorise_cat_log(cat_proc, color=False):
    """Print a Cylc log file in color at it would appear in the terminal.

    Args:
        cat_proc (subprocess.Process):
            A process which outputs a Cylc log file i.e. `cat`.
        color (bool):
            If `True` log will appear in color, if `False` no control
            characters will be added.

    """
    if color:
        color_proc = Popen(
            [
                'python3', '-c',
                '; '.join([
                    'import sys',
                    'from cylc.flow.loggingutil import re_formatter',
                    'print(re_formatter(sys.stdin.read()), end="")'
                ]),
            ],
            stdin=PIPE
        )
        color_proc.communicate(cat_proc.communicate()[0])
    else:
        cat_proc.wait()


def view_log(logpath, mode, tailer_tmpl, batchview_cmd=None, remote=False,
             color=False):
    """View (by mode) local log file. This is only called on the file host.

    batchview_cmd is a batch-system-specific job stdout or stderr cat or tail
    command (e.g. 'qcat') that may be implemented for batch systems that don't
    write logs to their final locations until after the job completes.

    If remote is True, we are executing on a remote host for a log file there.

    """
    # The log file path may contain '$USER' to be evaluated on the job host.
    if mode == 'print':
        # Print location even if the suite does not exist yet.
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
    elif not remote and mode == 'edit':
        # Copy the log to a temporary read-only file for viewing in editor.
        # Copy only BUFSIZE bytes at time, in case the file is huge.
        outfile = NamedTemporaryFile()
        with open(logpath, 'rb') as log:
            data = log.read(BUFSIZE)
            while data:
                outfile.write(data)
                data = log.read(BUFSIZE)
        os.chmod(outfile.name, S_IRUSR)
        outfile.seek(0, 0)
        return outfile
    elif mode == 'cat' or (remote and mode == 'edit'):
        # Just cat file contents to stdout.
        if batchview_cmd is not None:
            cmd = shlex.split(batchview_cmd)
        else:
            cmd = ['cat', logpath]
        proc1 = Popen(
            cmd,
            stdin=open(os.devnull),
            stdout=PIPE if color else None
        )
        colorise_cat_log(proc1, color=color)
        return 0
    elif mode == 'tail':
        if batchview_cmd is not None:
            cmd = batchview_cmd
        else:
            cmd = tailer_tmpl % {"filename": logpath}
        proc = Popen(shlex.split(cmd), stdin=open(os.devnull))
        with suppress(KeyboardInterrupt):
            watch_and_kill(proc)
        return proc.wait()


def get_option_parser():
    """Set up the CLI option parser."""
    parser = COP(
        __doc__, argdoc=[("REG", "Suite name"), ("[TASK-ID]", """Task ID""")])

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
        help="Suite log integer rotation number. 0 for current, 1 for "
        "next oldest, etc.",
        metavar="INT", action="store", dest="rotation_num")

    parser.add_option(
        "-o", "--force-remote",
        help="View remote logs remotely even if they have been retrieved"
        " to the suite host (default False).",
        action="store_true", default=False, dest="force_remote")

    parser.add_option(
        "-s", "--submit-number", "-t", "--try-number",
        help="Job submit number (default=%s, i.e. latest)." % NN,
        metavar="INT", action="store", dest="submit_num", default=NN)

    parser.add_option(
        "-g", "--geditor",
        help="edit mode: use your configured GUI editor.",
        action="store_true", default=False, dest="geditor")

    parser.add_option(
        "--remote-arg",
        help="(for internal use: continue processing on job host)",
        action="append", dest="remote_args")

    return parser


def get_task_job_attrs(suite_name, point, task, submit_num):
    """Return job (platform, batch_sys_name, live_job_id).

    live_job_id is batch system job ID if job is running, else None.

    """
    suite_dao = CylcSuiteDAO(
        get_suite_run_pub_db_name(suite_name), is_public=True)
    task_job_data = suite_dao.select_task_job(point, task, submit_num)
    suite_dao.close()
    if task_job_data is None:
        return (None, None, None)
    batch_sys_name = task_job_data["batch_sys_name"]
    batch_sys_job_id = task_job_data["batch_sys_job_id"]
    if (not batch_sys_name or not batch_sys_job_id
            or not task_job_data["time_run"]
            or task_job_data["time_run_exit"]):
        live_job_id = None
    else:
        live_job_id = batch_sys_job_id
    return (task_job_data["platform_name"], batch_sys_name, live_job_id)


def tmpfile_edit(tmpfile, geditor=False):
    """Edit a temporary read-only file containing the string filestr.

    Detect and warn if the user forcibly writes to the temporary file.

    """
    if geditor:
        editor = glbl_cfg().get(['editors', 'gui'])
    else:
        editor = glbl_cfg().get(['editors', 'terminal'])
    modtime1 = os.stat(tmpfile.name).st_mtime
    cmd = shlex.split(editor)
    cmd.append(tmpfile.name)
    proc = Popen(cmd, stderr=PIPE)
    err = proc.communicate()[1].decode()
    ret_code = proc.wait()
    if ret_code == 0:
        if os.stat(tmpfile.name).st_mtime > modtime1:
            sys.stderr.write(
                'WARNING: you edited a TEMPORARY COPY of %s\n' % (
                    os.path.basename(tmpfile.name)))
    if ret_code and err:
        sys.stderr.write(err)


@cli_function(get_option_parser)
def main(parser, options, *args, color=False):
    """Implement cylc cat-log CLI.

    Determine log path, user@host, batchview_cmd, and action (print, dir-list,
    cat, edit, or tail), and then if the log path is:
      a) local: perform action on log path, or
      b) remote: re-invoke cylc cat-log as a) on the remote account

    """
    if options.remote_args:
        # Invoked on job hosts for job logs only, as a wrapper to view_log().
        # Tail and batchview commands come from global config on suite host).
        logpath, mode, tail_tmpl = options.remote_args[0:3]
        logpath = os.path.expandvars(logpath)
        tail_tmpl = os.path.expandvars(tail_tmpl)
        try:
            batchview_cmd = options.remote_args[3]
        except IndexError:
            batchview_cmd = None
        res = view_log(logpath, mode, tail_tmpl, batchview_cmd, remote=True,
                       color=color)
        if res == 1:
            sys.exit(res)
        return

    suite_name = args[0]
    # Get long-format mode.
    try:
        mode = MODES[options.mode]
    except KeyError:
        mode = options.mode

    if len(args) == 1:
        # Cat suite logs, local only.
        if options.filename is not None:
            raise UserInputError("The '-f' option is for job logs only.")

        logpath = get_suite_run_log_name(suite_name)
        if options.rotation_num:
            logs = glob('%s.*' % logpath)
            logs.sort(key=os.path.getmtime, reverse=True)
            try:
                logpath = logs[int(options.rotation_num)]
            except IndexError:
                raise UserInputError(
                    "max rotation %d" % (len(logs) - 1))
        tail_tmpl = os.path.expandvars(forward_lookup()["tail command template"])
        out = view_log(logpath, mode, tail_tmpl, color=color)
        if out == 1:
            sys.exit(1)
        if mode == 'edit':
            tmpfile_edit(out, options.geditor)
        return

    if len(args) == 2:
        # Cat task job logs, may be on suite or job host.
        if options.rotation_num is not None:
            raise UserInputError(
                "only suite (not job) logs get rotated")
        task_id = args[1]
        try:
            task, point = TaskID.split(task_id)
        except ValueError:
            parser.error("Illegal task ID: %s" % task_id)
        if options.submit_num != NN:
            try:
                options.submit_num = "%02d" % int(options.submit_num)
            except ValueError:
                parser.error("Illegal submit number: %s" % options.submit_num)
        if options.filename is None:
            options.filename = JOB_LOG_OUT
        else:
            # Convert short filename args to long (e.g. 'o' to 'job.out').
            try:
                options.filename = JOB_LOG_OPTS[options.filename]
            except KeyError:
                # Is already long form (standard log, or custom).
                pass
        platform_name, batch_sys_name, live_job_id = get_task_job_attrs(
            suite_name, point, task, options.submit_num)
        platform = forward_lookup(platform_name)
        batchview_cmd = None
        if live_job_id is not None:
            # Job is currently running. Get special batch system log view
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
                try:
                    batchview_cmd_tmpl = platform[conf_key]
                except KeyError:
                    pass
                if batchview_cmd_tmpl is not None:
                    batchview_cmd = batchview_cmd_tmpl % {
                        "job_id": str(live_job_id)}

        log_is_remote = (is_remote_platform(platform)
                         and (options.filename not in JOB_LOGS_LOCAL))
        log_is_retrieved = (platform['retrieve job logs']
                            and live_job_id is None)
        if log_is_remote and (not log_is_retrieved or options.force_remote):
            logpath = os.path.normpath(get_remote_suite_run_job_dir(
                platform,
                suite_name, point, task, options.submit_num, options.filename))
            tail_tmpl = platform["tail command template"]
            # Reinvoke the cat-log command on the remote account.
            cmd = ['cat-log']
            if cylc.flow.flags.debug:
                cmd.append('--debug')
            for item in [logpath, mode, tail_tmpl]:
                cmd.append('--remote-arg=%s' % quote(item))
            if batchview_cmd:
                cmd.append('--remote-arg=%s' % quote(batchview_cmd))
            cmd.append(suite_name)
            is_edit_mode = (mode == 'edit')
            try:
                host = get_host_from_platform(platform)
                user = getuser()
                proc = remote_cylc_cmd(
                    cmd, user, host, capture_process=is_edit_mode,
                    manage=(mode == 'tail'))
            except KeyboardInterrupt:
                # Ctrl-C while tailing.
                pass
            else:
                if is_edit_mode:
                    # Write remote stdout to a temp file for viewing in editor.
                    # Only BUFSIZE bytes at a time in case huge stdout volume.
                    out = NamedTemporaryFile()
                    data = proc.stdout.read(BUFSIZE)
                    while data:
                        out.write(data)
                        data = proc.stdout.read(BUFSIZE)
                    os.chmod(out.name, S_IRUSR)
                    out.seek(0, 0)
        else:
            # Local task job or local job log.
            logpath = os.path.normpath(get_suite_run_job_dir(
                suite_name, point, task, options.submit_num, options.filename))
            tail_tmpl = os.path.expandvars(platform["tail command template"])
            out = view_log(logpath, mode, tail_tmpl, batchview_cmd,
                           color=color)
            if mode != 'edit':
                sys.exit(out)
        if mode == 'edit':
            tmpfile_edit(out, options.geditor)


if __name__ == "__main__":
    main()
