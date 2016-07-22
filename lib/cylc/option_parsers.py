#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2016 NIWA
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
"""Common options for all cylc commands."""

from optparse import OptionParser, OptionConflictError
import os
import re
import cylc.flags
from cylc.owner import USER
from cylc.registration import RegistrationDB, RegistrationError
from cylc.regpath import IllegalRegPathError


class DBOptParse(object):
    def __init__(self, dbopt):
        # input is DB option spec from the cylc command line
        self.owner = USER
        self.location = None
        if dbopt:
            self.parse(dbopt)

    def parse(self, dbopt):
        # determine DB location and owner
        if dbopt.startswith('u:'):
            self.owner = dbopt[2:]
            dbopt = os.path.join('~' + self.owner, '.cylc', 'DB')
        if dbopt.startswith('~'):
            dbopt = os.path.expanduser(dbopt)
        else:
            dbopt = os.path.abspath(dbopt)
        self.location = dbopt

    def get_db_owner(self):
        return self.owner

    def get_db_location(self):
        return self.location


class CylcOptionParser(OptionParser):

    """Common options for all cylc CLI commands."""

    MULTITASK_USAGE = """
A TASKID is an identifier for matching individual task proxies and/or families
of them. It can be written in these syntaxes:
* [CYCLE-POINT-GLOB/]TASK-NAME-GLOB[:TASK-STATE]
* [CYCLE-POINT-GLOB/]FAMILY-NAME-GLOB[:TASK-STATE]
* TASK-NAME-GLOB[.CYCLE-POINT-GLOB][:TASK-STATE]
* FAMILY-NAME-GLOB[.CYCLE-POINT-GLOB][:TASK-STATE]

For example, to match:
* all tasks in a cycle: '20200202T0000Z/*' or '*.20200202T0000Z'
* all tasks in the submitted status: ':submitted'
* retrying 'foo*' tasks in 0000Z cycles: 'foo*.*0000Z:retrying' or
  '*0000Z/foo*:retrying'
* retrying tasks in 'BAR' family: '*/BAR:retrying' or 'BAR.*:retrying'
* retrying tasks in 'BAR' or 'BAZ' families: '*/BA[RZ]:retrying' or
  'BA[RZ].*:retrying'

The old 'MATCH POINT' syntax will be automatically detected and supported. To
avoid this, use the '--no-multitask-compat' option, or use the new syntax
(with a '/' or a '.') when specifying 2 TASKID arguments."""

    def __init__(self, usage, argdoc=None, pyro=False, noforce=False,
                 jset=False, multitask=False, prep=False, twosuites=False,
                 auto_add=True):

        self.auto_add = auto_add
        if argdoc is None:
            if not prep:
                argdoc = [('REG', 'Suite name')]
            else:
                argdoc = [('SUITE', 'Suite name or path')]

        # noforce=True is for commands that don't use interactive prompts at
        # all

        if multitask:
            usage += self.MULTITASK_USAGE
        usage += """

Arguments:"""
        args = ""
        self.n_compulsory_args = 0
        self.n_optional_args = 0
        self.unlimited_args = False
        self.pyro = pyro
        self.jset = jset
        self.noforce = noforce

        self.multitask = multitask

        self.prep = prep
        self.suite_info = []
        self.twosuites = twosuites

        maxlen = 0
        for arg in argdoc:
            if len(arg[0]) > maxlen:
                maxlen = len(arg[0])

        for arg in argdoc:
            if arg[0].startswith('['):
                self.n_optional_args += 1
            else:
                self.n_compulsory_args += 1
            if arg[0].endswith('...]'):
                self.unlimited_args = True

            args += arg[0] + " "

            pad = (maxlen - len(arg[0])) * ' ' + '               '
            usage += "\n   " + arg[0] + pad + arg[1]

        usage = re.sub('ARGS', args, usage)

        OptionParser.__init__(self, usage)

    def add_std_options(self):
        """Add standard options if they have not been overridden."""
        try:
            self.add_option(
                "--user",
                help=(
                    "Other user account name. This results in "
                    "command reinvocation on the remote account."
                ),
                metavar="USER", default=USER,
                action="store", dest="owner")
        except OptionConflictError:
            pass

        try:
            self.add_option(
                "--host",
                help="Other host name. This results in "
                "command reinvocation on the remote account.",
                metavar="HOST", action="store", dest="host")
        except OptionConflictError:
            pass

        try:
            self.add_option(
                "-v", "--verbose",
                help="Verbose output mode.",
                action="store_true", default=False, dest="verbose")
        except OptionConflictError:
            pass

        try:
            self.add_option(
                "--debug",
                help=(
                    "Run suites in non-daemon mode, "
                    "and show exception tracebacks."
                ),
                action="store_true", default=False, dest="debug")
        except OptionConflictError:
            pass

        try:
            self.add_option(
                "--db",
                help=(
                    "Alternative suite registration database location, "
                    "defaults to $HOME/.cylc/REGDB."
                ),
                metavar="PATH", action="store", default=None, dest="db")
        except OptionConflictError:
            pass

        if self.pyro:
            try:
                self.add_option(
                    "--port",
                    help=(
                        "Suite port number on the suite host. "
                        "NOTE: this is retrieved automatically if "
                        "non-interactive ssh is configured to the suite host."
                    ),
                    metavar="INT", action="store", default=None, dest="port")
            except OptionConflictError:
                pass

            try:
                self.add_option(
                    "--use-ssh",
                    help="Use ssh to re-invoke the command on the suite host.",
                    action="store_true", default=False, dest="use_ssh")
            except OptionConflictError:
                pass

            try:
                self.add_option(
                    "--no-login",
                    help=(
                        "Do not use a login shell to run remote ssh commands. "
                        "The default is to use a login shell."
                    ),
                    action="store_false", default=True, dest="ssh_login")
            except OptionConflictError:
                pass

            try:
                self.add_option(
                    "--pyro-timeout", metavar='SEC',
                    help=(
                        "Set a timeout for network connections "
                        "to the running suite. The default is no timeout. "
                        "For task messaging connections see "
                        "site/user config file documentation."
                    ),
                    action="store", default=None, dest="pyro_timeout")
            except OptionConflictError:
                pass

            try:
                self.add_option(
                    "--print-uuid",
                    help=(
                        "Print the client UUID to stderr. "
                        "This can be matched "
                        "to information logged by the receiving suite daemon."
                    ),
                    action="store_true", default=False, dest="print_uuid")
            except OptionConflictError:
                pass

            try:
                self.add_option(
                    "--set-uuid", metavar="UUID",
                    help=(
                        "Set the client UUID manually (e.g. from prior use of "
                        "--print-uuid). This can be used to log multiple "
                        "commands under the same UUID (but note that only the "
                        "first [info] command from the same client ID will be "
                        "logged unless the suite is running in debug mode)."
                    ),
                    action="store", default=None, dest="set_uuid")
            except OptionConflictError:
                pass

            if not self.noforce:
                try:
                    self.add_option(
                        "-f", "--force",
                        help=(
                            "Do not ask for confirmation before acting. "
                            "Note that it is not necessary to use this option "
                            "if interactive command prompts have been "
                            "disabled in the site/user config files."
                        ),
                        action="store_true", default=False, dest="force")
                except OptionConflictError:
                    pass

        if self.jset:
            try:
                self.add_option(
                    "-s", "--set", metavar="NAME=VALUE",
                    help=(
                        "Set the value of a Jinja2 template variable in the "
                        "suite definition. This option can be used multiple "
                        "times on the command line. "
                        "WARNING: these settings do not persist across suite "
                        "restarts; "
                        "they need to be set again on the \"cylc restart\" "
                        "command line."
                    ),
                    action="append", default=[], dest="templatevars")
            except OptionConflictError:
                pass

            try:
                self.add_option(
                    "--set-file", metavar="FILE",
                    help=(
                        "Set the value of Jinja2 template variables in the "
                        "suite definition from a file containing NAME=VALUE "
                        "pairs (one per line). "
                        "WARNING: these settings do not persist across suite "
                        "restarts; "
                        "they need to be set again on the \"cylc restart\" "
                        "command line."
                    ),
                    action="store", default=None, dest="templatevars_file")
            except OptionConflictError:
                pass

        if self.multitask:
            try:
                self.add_option(
                    "-m", "--family",
                    help=(
                        "(Obsolete) This option is now ignored "
                        "and is retained for backward compatibility only. "
                        "TASKID in the argument list can be used to match "
                        "task and family names regardless of this option."),
                    action="store_true", default=False, dest="is_family")
            except OptionConflictError:
                pass

            try:
                self.add_option(
                    "--no-multitask-compat",
                    help="Disallow backward compatible multitask interface.",
                    action="store_false", default=True,
                    dest="multitask_compat")
            except OptionConflictError:
                pass

    def get_suite(self, index=0):
        """Return suite name."""
        return self.suite_info[index]

    def _getdef(self, arg, options):
        """Return (suite_name, suite_rc_path).

        If arg is a registered suite, suite name is the registered suite name.
        If arg is a directory, suite name is the name of the directory.
        If arg is a file, suite name is the name of its container directory.

        """
        reg_db = RegistrationDB(options.db)
        try:
            path = reg_db.get_suiterc(arg)
            name = arg
        except (IllegalRegPathError, RegistrationError):
            arg = os.path.abspath(arg)
            if os.path.isdir(arg):
                path = os.path.join(arg, 'suite.rc')
                name = os.path.basename(arg)
            else:
                path = arg
                name = os.path.basename(os.path.dirname(arg))
        return name, path

    def parse_args(self, remove_opts=[]):
        """Parse options and arguments, overrides OptionParser.parse_args."""
        if self.auto_add:
            # Add common options after command-specific options.
            self.add_std_options()

        for opt in remove_opts:
            try:
                self.remove_option(opt)
            except:
                pass

        (options, args) = OptionParser.parse_args(self)

        if len(args) < self.n_compulsory_args:
            self.error("Wrong number of arguments (too few)")

        elif not self.unlimited_args and \
                len(args) > self.n_compulsory_args + self.n_optional_args:
            self.error("Wrong number of arguments (too many)")

        foo = DBOptParse(options.db)
        options.db = foo.get_db_location()
        options.db_owner = foo.get_db_owner()

        if self.jset:
            if options.templatevars_file:
                options.templatevars_file = os.path.abspath(os.path.expanduser(
                    options.templatevars_file))

        if self.prep:
            # allow file path or suite name
            try:
                self.suite_info.append(self._getdef(args[0], options))
                if self.twosuites:
                    self.suite_info.append(self._getdef(args[1], options))
            except IndexError:
                if options.filename:
                    # Empty args list is OK if we supplied a filename
                    pass
                else:
                    # No filename, so we're expecting an argument
                    self.error("Need either a filename or suite name(s)")

        cylc.flags.verbose = options.verbose
        cylc.flags.debug = options.debug

        return (options, args)

    @classmethod
    def parse_multitask_compat(cls, options, mtask_args):
        """Parse argument items for multitask backward compatibility.

        If options.multitask_compat is False, return (mtask_args, None).

        If options.multitask_compat is True, it checks if mtask_args is a
        2-element array and if the 1st and 2nd arguments look like the old
        "MATCH" "POINT" CLI arguments.
        If so, it returns (mtask_args[0], mtask_args[1]).
        Otherwise, it return (mtask_args, None).

        """
        if (options.multitask_compat and len(mtask_args) == 2 and
                all(["/" not in mtask_arg for mtask_arg in mtask_args]) and
                "." not in mtask_args[1]):
            # For backward compat, argument list should have 2 elements.
            # Element 1 may be a regular expression, so it may contain "." but
            # should not contain a "/".
            # All other elements should contain no "." and "/".
            return (mtask_args[0], mtask_args[1])
        else:
            return (mtask_args, None)
