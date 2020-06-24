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

"""cylc [discovery] check-versions [OPTIONS] ARGS

Check the version of cylc invoked on each of SUITE's task host accounts when
CYLC_VERSION is set to *the version running this command line tool*.
Different versions are reported but are not considered an error unless the
-e|--error option is specified, because different cylc versions from 6.0.0
onward should at least be backward compatible.

It is recommended that cylc versions be installed in parallel and access
configured via the cylc version wrapper as described in the cylc INSTALL
file and User Guide. This must be done on suite and task hosts. Users then get
the latest installed version by default, or (like tasks) a particular version
if $CYLC_VERSION is defined.

Use -v/--verbose to see the command invoked to determine the remote version
(all remote cylc command invocations will be of the same form, which may be
site dependent -- see cylc global config documentation."""

import os
import sys
from time import sleep

import cylc.flow.flags
from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.cylc_subproc import procopen
from cylc.flow import __version__ as CYLC_VERSION
from cylc.flow.config import SuiteConfig
from cylc.flow.subprocpool import SubProcPool
from cylc.flow.suite_files import parse_suite_arg
from cylc.flow.task_remote_mgr import TaskRemoteMgr
from cylc.flow.templatevars import load_template_vars
from cylc.flow.terminal import cli_function


def get_option_parser():
    parser = COP(__doc__, prep=True, jset=True)

    parser.add_option(
        "-e", "--error", help="Exit with error status "
        "if " + CYLC_VERSION + " is not available on all remote accounts.",
        action="store_true", default=False, dest="error")

    return parser


@cli_function(get_option_parser, remove_opts=['--host', '--user'])
def main(_, options, *args):
    # suite name or file path
    suite, suiterc = parse_suite_arg(options, args[0])

    # extract task host accounts from the suite
    config = SuiteConfig(
        suite,
        suiterc,
        options,
        load_template_vars(options.templatevars, options.templatevars_file))
    account_set = set()
    for name in config.get_namespace_list('all tasks'):
        account_set.add((
            config.get_config(['runtime', name, 'remote', 'owner']),
            config.get_config(['runtime', name, 'remote', 'host'])))
    task_remote_mgr = TaskRemoteMgr(suite, SubProcPool())
    for _, host_str in account_set:
        task_remote_mgr.remote_host_select(host_str)
    accounts = []
    while account_set:
        for user, host_str in account_set.copy():
            res = task_remote_mgr.remote_host_select(host_str)
            if res:
                account_set.remove((user, host_str))
                accounts.append((user, res))
        if account_set:
            task_remote_mgr.proc_pool.process()
            sleep(1.0)

    # Interrogate the each remote account with CYLC_VERSION set to our version.
    # Post backward compatibility concerns to do this we can just run:
    #   cylc version --host=HOST --user=USER
    # but this command only exists for version > 6.3.0.
    # So for the moment generate an actual remote invocation command string for
    # "cylc --version".

    verbose = cylc.flow.flags.verbose

    warn = {}
    contacted = 0
    for user, host in sorted(accounts):
        argv = ["cylc", "version"]
        if user and host:
            argv += ["--user=%s" % user, "--host=%s" % host]
            user_at_host = "%s@%s" % (user, host)
        elif user:
            argv += ["--user=%s" % user]
            user_at_host = "%s@localhost" % user
        elif host:
            argv += ["--host=%s" % host]
            user_at_host = host
        if verbose:
            print("%s: %s" % (user_at_host, ' '.join(argv)))
        proc = procopen(argv, stdin=open(os.devnull), stdoutpipe=True,
                        stderrpipe=True)
        out, err = proc.communicate()
        out = out.decode()
        err = err.decode()
        if proc.wait() == 0:
            if verbose:
                print("   %s" % out)
            contacted += 1
            out = out.strip()
            if out != CYLC_VERSION:
                warn[user_at_host] = out
        else:
            print('ERROR ' + user_at_host + ':', file=sys.stderr)
            print(err, file=sys.stderr)

    # report results
    if not warn:
        if contacted:
            print("All", contacted, "accounts have cylc-" + CYLC_VERSION)
    else:
        print("WARNING: failed to invoke cylc-%s on %d accounts:" % (
            CYLC_VERSION, len(warn)))
        m = max(len(ac) for ac in warn)
        for ac, warning in warn.items():
            print(' ', ac.ljust(m), warning)
        if options.error:
            sys.exit(1)


if __name__ == "__main__":
    main()
