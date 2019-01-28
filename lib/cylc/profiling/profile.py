# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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
"""Performs profiling of cylc.

System calls to cylc are performed here.

"""

import os
import shutil
from subprocess import Popen, PIPE, call
import sys
import tempfile
import time
import traceback

from . import (PROFILE_MODE_TIME, PROFILE_MODE_CYLC, PROFILE_MODES,
               PROFILE_FILES, SUITE_STARTUP_STRING)
from .analysis import extract_results
from .git import (checkout, describe, GitCheckoutError,)


def cylc_env(cylc_conf_path=''):
    """Provide an environment for executing cylc commands in."""
    env = os.environ.copy()
    env['CYLC_CONF_PATH'] = cylc_conf_path
    return env


CLEAN_ENV = cylc_env()


class SuiteFailedException(Exception):
    """Exception to handle the failure of a suite-run / validate command."""

    MESSAGE = '''ERROR: "{cmd}" returned a non-zero code.'
    stdout: {stdout}
    stderr: {stderr}'''

    def __init__(self, cmd, stdout, stderr):
        self.cmd = '$ ' + ' '.join(cmd)
        self.stdout = stdout
        self.stderr = stderr
        Exception.__init__(self, str(self))

    def __str__(self):
        return self.MESSAGE.format(cmd=self.cmd, stdout=self.stdout,
                                   stderr=self.stderr)


class ProfilingKilledException(SuiteFailedException):
    """Exception to handle the event that a user has canceled profiling whilst
    a suite is running."""
    pass


def cylc_major_version():
    """Return the first character of the cylc version e.g. '7'."""
    return Popen(
        ['cylc', '--version'], env=CLEAN_ENV, stdin=open(os.devnull),
        stdout=PIPE).communicate()[0].decode().strip()[0]


def register_suite(reg, sdir):
    """Registers the suite located in sdir with the registration name reg."""
    cmd = ['cylc', 'register', reg, sdir]
    print('$ ' + ' '.join(cmd))
    if not call(cmd, stdin=open(os.devnull), stdout=PIPE, env=CLEAN_ENV):
        return True
    print('\tFailed')
    return False


def unregister_suite(reg):
    """Unregisters the suite reg."""
    cmd = ['cylc', 'unregister', reg]
    print('$ ' + ' '.join(cmd))
    call(cmd, stdin=open(os.devnull), stdout=PIPE, env=CLEAN_ENV)


def purge_suite(reg):
    """Deletes the run directory for this suite."""
    print('$ rm -rf ' + os.path.expanduser(os.path.join('~', 'cylc-run', reg)))
    try:
        shutil.rmtree(os.path.expanduser(os.path.join('~', 'cylc-run', reg)))
    except OSError:
        return False
    else:
        return True


def run_suite(reg, options, out_file, profile_modes, mode='live',
              conf_path=''):
    """Runs cylc run / cylc validate on the provided suite with the requested
    profiling options.

    Arguments:
        reg (str): The registration of the suite to run.
        options (list): List of jinja2 setting=value pairs.
        out_file (str): The file to redirect stdout to.
        profile_modes (list): List of profiling systems to employ
            (i.e. cylc, time).
        mode (str - optional): The mode to run the suite in, simulation, dummy,
            live or validate.

    Returns:
        str - The path to the suite stderr if any is present.

    """
    cmds = []
    env = cylc_env(cylc_conf_path=conf_path)

    # Cylc profiling, echo command start time.
    if PROFILE_MODE_CYLC in profile_modes:
        cmds += ['echo', SUITE_STARTUP_STRING, r'$(date +%s.%N)', '&&']

    # /usr/bin/time profiling.
    if PROFILE_MODE_TIME in profile_modes:
        if sys.platform == 'darwin':  # MacOS
            cmds += ['/usr/bin/time', '-lp']
        else:  # Assume Linux
            cmds += ['/usr/bin/time', '-v']

        # Run using `sh -c` to enable the redirection of output (darwins
        # /usr/bin/time command does not have a -o option).
        cmds += ['sh', '-c', "'"]

    # Cylc run.
    run_cmds = []
    if mode == 'validate':
        run_cmds = ['cylc', 'validate']
    elif mode == 'profile-simulation':
        # In simulation mode task scripts are manually replaced with sleep 1.
        run_cmds = ['cylc', 'run', '--mode', 'live']
    else:
        run_cmds = ['cylc', 'run', '--mode', mode]
    run_cmds += [reg]
    cmds += run_cmds

    # Jinja2 params.
    jinja2_params = ['-s {0}'.format(option) for option in options]
    if mode == 'profile-simulation':
        # Add namespaces jinja2 param (list of task names).
        tmp = ['-s namespaces=root']
        namespaces = Popen(
            ['cylc', 'list', reg] + jinja2_params + tmp,
            stdin=open(os.devnull), stdout=PIPE,
            env=env).communicate()[0].decode().split() + ['root']
        jinja2_params.append(
            '-s namespaces={0}'.format(','.join(namespaces)))
    cmds.extend(jinja2_params)

    # Cylc profiling.
    if PROFILE_MODE_CYLC in profile_modes:
        if mode == 'validate':
            sys.exit('ERROR: profile_mode "cylc" not possible in validate '
                     'mode')
        else:
            cmds += ['--profile']

    # No-detach mode.
    if mode != 'validate':
        cmds += ['--no-detach']

    # Redirect output.
    cmd_out = out_file + PROFILE_FILES['cmd-out']
    cmd_err = out_file + PROFILE_FILES['cmd-err']
    time_err = out_file + PROFILE_FILES['time-err']
    startup_file = out_file + PROFILE_FILES['startup']
    cmds += ['>', cmd_out, '2>', cmd_err]
    if PROFILE_MODE_TIME in profile_modes:
        cmds += ["'"]  # Close shell.

    # Execute.
    print('$ ' + ' '.join(cmds))
    try:
        proc = Popen(' '.join(cmds), shell=True, stderr=open(time_err, 'w+'),
                     stdout=open(startup_file, 'w+'), env=env)
        if proc.wait():
            raise SuiteFailedException(run_cmds, cmd_out, cmd_err)
    except KeyboardInterrupt:
        kill_cmd = ['cylc', 'stop', '--kill', reg]
        print('$ ' + ' '.join(kill_cmd))
        call(kill_cmd, env=env, stdin=open(os.devnull))
        raise ProfilingKilledException(run_cmds, cmd_out, cmd_err)

    # Return cylc stderr if present.
    try:
        if os.path.getsize(cmd_err) > 0:
            return cmd_err
    except OSError:
        pass
    return None


def run_experiment(exp):
    """Run the provided experiment with the currently checked-out cylc version.

    Return a dictionary of result files by run name.

    """
    profile_modes = [PROFILE_MODES[mode] for mode in exp['profile modes']]
    cylc_maj_version = cylc_major_version()
    result_files = {}
    to_purge = []
    for run in exp['runs']:
        results_for_run = []
        sdir = os.path.expanduser(run['suite dir'])
        reg = 'profile-' + str(time.time()).replace('.', '')
        count = 0
        while count < run['repeats'] + 1:
            # Run suite.
            out_file = tempfile.mkstemp()[1]
            results_for_run.append(out_file)
            register_suite(reg, sdir)
            err_file = run_suite(
                reg,
                run['options'] + ['cylc_compat_mode=%s' % cylc_maj_version],
                out_file,
                profile_modes,
                exp.get('mode', 'live'),
                conf_path=run.get('globalrc', ''))
            # Handle errors.
            if err_file:
                print(('WARNING: non-empty suite error log: ' +
                                      err_file), file=sys.stderr)
            # Tidy up.
            if cylc_maj_version == '6':
                unregister_suite(reg)
            if not purge_suite(reg):
                # Remove suite run dirs, if error then try again later.
                to_purge.append(reg)
            count += 1
        result_files[run['name']] = results_for_run

        if to_purge:
            time.sleep(2)  # Wait a bit before trying again to remove run dirs.
        for reg in to_purge:
            if purge_suite(reg):
                to_purge.remove(reg)

        if to_purge:
            print(('ERROR: The following suite(s) run '
                                  'directories could not be deleted:\n'
                                  '\t' + ' '.join(to_purge)
                                  ), file=sys.stderr)

    return result_files


def delete_result_files(result_files):
    """Deletes the temp files used to store experiment results."""
    for files in result_files.values():
        for file_ in files:
            for suffix in PROFILE_FILES.values():
                try:
                    os.remove(file_ + suffix)
                except OSError:
                    pass


def profile(schedule):
    """Perform profiling for the provided schedule.

    Args:
        schedule (list): A list of tuples of the form
            [(version_id, experiments)] where experiments is a list of
            experiment objects.

    Returns:
        tuple - (results, checkout_count, success)
          - results (dict) - A dictionary containing profiling results in the
            form {version_id: experiment_id: metric: value}.
          - checkout_count (int) - The number of times the git checkout command
            has been executed.
          - success (bool) - True if all experiments completed successfully,
            else False.
    """
    checkout_count = 0
    results = {}
    success = True
    for version_id, experiments in sorted(schedule.items()):
        # Checkout cylc version.
        if version_id != describe():
            try:
                checkout(version_id, delete_pyc=True)
                checkout_count += 1
            except GitCheckoutError:
                sys.exit('Error: git checkout failed, were changes made to the'
                         ' working copy?')

        # Run Experiment.
        for experiment in experiments:
            try:
                result_files = run_experiment(experiment['config'])
            except ProfilingKilledException as exc:
                # Profiling has been terminated, return what results we have.
                print(exc)
                return results, checkout_count, False
            except SuiteFailedException as exc:
                # Experiment failed to run, move onto the next one.
                print(('Experiment "%s" failed at version "%s"'
                                      '' % (experiment['name'], version_id)), file=sys.stderr)
                print(exc, file=sys.stderr)
                success = False
                continue
            else:
                # Run analysis.
                try:
                    processed_results = extract_results(
                        result_files, experiment['config'])
                except Exception:
                    # Analysis failed, move onto the next experiment.
                    traceback.print_exc()
                    exp_files = []
                    for run in result_files:
                        exp_files.extend(result_files[run])
                    print((
                        'Analysis failed on results from experiment "%s" '
                        'running at version "%s".\n\tProfile files: %s' % (
                            experiment['name'],
                            version_id,
                            ' '.join(exp_files))), file=sys.stderr)
                    if any(PROFILE_MODES[mode] == PROFILE_MODE_CYLC
                            for mode in experiment['config']['profile modes']):
                        print((
                            'Are you trying to use profile mode "cylc" '
                            'with an older version of cylc?'), file=sys.stderr)
                    success = False
                    continue
                else:
                    if version_id not in results:
                        results[version_id] = {}
                    results[version_id][experiment['id']] = (
                        processed_results)
                    delete_result_files(result_files)

    return results, checkout_count, success
