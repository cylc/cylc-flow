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
"""Simple suite name registration database."""

import os
import random
import re
import shlex
from string import ascii_letters, digits
from subprocess import Popen, PIPE
import sys
from tempfile import NamedTemporaryFile
import traceback

from cylc.cfgspec.globalcfg import GLOBAL_CFG
import cylc.flags
from cylc.mkdir_p import mkdir_p
from cylc.owner import USER, is_remote_user
from cylc.regpath import RegPath
from cylc.suite_host import get_hostname, is_remote_host

REGDB_PATH = os.path.join(os.environ['HOME'], '.cylc', 'REGDB')


class PassphraseError(ValueError):
    """Raised on error if passphrase file does not contain a good value."""

    def __str__(self):
        return "ERROR: invalid content in passphrase file: %s" % self.args


class RegistrationError(Exception):
    """Raise on suite registration error."""
    pass


class RegistrationDB(object):
    """Represents a simple suite name registration database."""

    PASSPHRASES_DIR_BASE = 'passphrases'
    PASSPHRASE_FILE_BASE = 'passphrase'
    PASSPHRASE_CHARSET = ascii_letters + digits
    PASSPHRASE_LEN = 20

    def __init__(self, dbpath=None):
        self.dbpath = dbpath or REGDB_PATH
        # create initial database directory if necessary
        if not os.path.exists(self.dbpath):
            try:
                mkdir_p(self.dbpath)
            except OSError as exc:
                sys.exit(str(exc))
        self.local_passphrases = set()
        self.cached_passphrases = {}

    def cache_passphrase(self, suite, owner, host, passphrase):
        """Cache and dump passphrase for a remote suite in standard location.

        Save passphrase to ~/.cylc/passphrases/owner@host/suite if possible.
        This is normally called on a successful authentication, and will cache
        the remote passphrase in memory as well.
        """
        if owner is None:
            owner = USER
        if host is None:
            host = get_hostname()
        path = os.path.expanduser(os.path.join(
            '~', '.cylc', self.PASSPHRASES_DIR_BASE, owner + "@" + host, suite
        ))
        self.cached_passphrases[(suite, owner, host)] = passphrase
        # Dump to a file only for remote suites
        if is_remote_user(owner) or is_remote_host(host):
            # Although not desirable, failing to dump the passphrase to a file
            # is not disastrous.
            try:
                self._dump_passphrase_to_dir(path, passphrase)
            except (IOError, OSError):
                if cylc.flags.debug:
                    traceback.print_exc()

    def _dump_passphrase_to_dir(self, path, passphrase=None):
        """Dump passphrase to "passphrase" file in "path".

        1. File permission should already be user-read-write-only on
           creation by mkstemp.
        2. The combination of os.fsync and os.rename should guarentee
           that we don't end up with an incomplete passphrase file.
        3. Perhaps we should use uuid.uuid4() to generate the passphrase?
        """
        mkdir_p(path)
        handle = NamedTemporaryFile(
            prefix=self.PASSPHRASE_FILE_BASE, dir=path, delete=False)
        # Note: Perhaps a UUID might be better here?
        if passphrase is None:
            passphrase = ''.join(
                random.sample(self.PASSPHRASE_CHARSET, self.PASSPHRASE_LEN))
        handle.write(passphrase)
        os.fsync(handle.fileno())
        handle.close()
        passphrase_file_name = os.path.join(
            path, self.PASSPHRASE_FILE_BASE)
        os.rename(handle.name, passphrase_file_name)
        if cylc.flags.verbose:
            print 'Generated suite passphrase: %s' % passphrase_file_name

    def dump_suite_data(self, suite, data):
        """Dump suite path and title in text file."""
        with open(os.path.join(self.dbpath, suite), 'w') as handle:
            handle.write('path=%(path)s\ntitle=%(title)s\n' % data)

    def list_all_suites(self):
        """Return a list containing names of registered suites."""
        try:
            suites = os.listdir(self.dbpath)
        except OSError as exc:
            sys.exit(str(exc))
        return suites

    def load_all_passphrases(self):
        """Load all of user's passphrases on ~/.cylc/.

        (back-compat for <= 6.4.1).
        """
        if self.local_passphrases:
            return self.local_passphrases

        # Find passphrases in all registered suite directories.
        for items in self.get_list():
            # items = suite, path, title
            try:
                self.local_passphrases.add(
                    self.load_passphrase_from_dir(items[1]))
            except (IOError, PassphraseError):
                if cylc.flags.debug:
                    traceback.print_exc()

        # Find all passphrases installed under ~/.cylc/
        for items in os.walk(os.path.expanduser('~/.cylc')):
            # items = dirpath, dirnames, filenames
            try:
                self.local_passphrases.add(
                    self.load_passphrase_from_dir(items[0]))
            except (IOError, PassphraseError):
                if cylc.flags.debug:
                    traceback.print_exc()

        return self.local_passphrases

    def load_passphrase(self, suite, owner, host, cache_ok=True):
        """Search for passphrase file for suite, load and return content.

        "passphrase" file is searched from these locations in order:

        1/ For running task jobs:
           a/ $CYLC_SUITE_RUN_DIR then $CYLC_SUITE_DEF_PATH for remote jobs.
           b/ $CYLC_SUITE_DEF_PATH_ON_SUITE_HOST for local jobs or remote jobs
              with SSH messaging.

        2/ For suite on local user@host. The suite definition directory, as
           registered. (Note: Previously, this needs to be the 1st location,
           else sub-suites load their parent suite's passphrase on start-up
           because the "cylc run" command runs in a parent suite task execution
           environment. This problem no longer exists becase on suite start up,
           the "load_passphrase_from_dir" method is called directly instead of
           through this method.)

        3/ From memory cache, for passphrases of remote suites.
           Don't use if cache_ok=False.

        4/ Locations under $HOME/.cylc/ for remote suite control from accounts
           that do not actually need the suite definition directory to be
           installed (a/ is now preferred. b/ c/ d/ are for back compat):
           a/ $HOME/.cylc/passphrases/SUITE_OWNER@SUITE_HOST/SUITE_NAME/
           b/ $HOME/.cylc/SUITE_HOST/SUITE_OWNER/SUITE_NAME/
           c/ $HOME/.cylc/SUITE_HOST/SUITE_NAME/
           d/ $HOME/.cylc/SUITE_NAME/
           Don't use if cache_ok=False.

        5/ For remote suites, try locating the passphrase file from suite
           definition directory on remote owner@host via SSH.

        """
        # (1 before 2 else sub-suites load their parent suite's
        # passphrase on start-up because the "cylc run" command runs in
        # a parent suite task execution environment).

        # 1/ Running tasks: suite def dir from the task execution environment.
        # Test for presence of task execution environment
        suite_host = os.getenv('CYLC_SUITE_HOST')
        suite_owner = os.getenv('CYLC_SUITE_OWNER')
        env_keys = []
        if is_remote_host(suite_host) or is_remote_user(suite_owner):
            # 2(i)/ Task messaging call on a remote account.
            # First look in the remote suite run directory than suite
            # definition directory ($CYLC_SUITE_DEF_PATH is modified
            # for remote tasks):
            env_keys = ['CYLC_SUITE_RUN_DIR', 'CYLC_SUITE_DEF_PATH']
        elif suite_host or suite_owner:
            # 2(ii)/ Task messaging call on the suite host account.

            # Could be a local task or a remote task with 'ssh
            # messaging = True'. In either case use
            # $CYLC_SUITE_DEF_PATH_ON_SUITE_HOST which never
            # changes, not $CYLC_SUITE_DEF_PATH which gets
            # modified for remote tasks as described above.
            env_keys = ['CYLC_SUITE_DEF_PATH_ON_SUITE_HOST']
        for env_key in env_keys:
            try:
                return self.load_passphrase_from_dir(os.environ[env_key])
            except (KeyError, IOError, PassphraseError):
                pass

        # 2/ Cylc commands with suite definition directory from local reg.
        if owner is None:
            owner = USER
        if host is None:
            host = get_hostname()

        if not is_remote_user(owner) and not is_remote_host(host):
            try:
                return self.load_passphrase_from_dir(self.get_suitedir(suite))
            except (IOError, PassphraseError, RegistrationError):
                pass

        # 3/ From memory cache
        if cache_ok and (suite, owner, host) in self.cached_passphrases:
            return self.cached_passphrases[(suite, owner, host)]

        # 4/ Other allowed locations, as documented above.
        # For remote control commands, host here will be fully
        # qualified or not depending on what's given on the command line.
        if cache_ok:
            short_host = host.split('.', 1)[0]
            prefix = os.path.expanduser(os.path.join('~', '.cylc'))
            paths = []
            for names in [
                    (prefix, self.PASSPHRASES_DIR_BASE,
                     owner + "@" + host, suite),
                    (prefix, self.PASSPHRASES_DIR_BASE,
                     owner + "@" + short_host, suite),
                    (prefix, host, owner, suite),
                    (prefix, short_host, owner, suite),
                    (prefix, host, suite),
                    (prefix, short_host, suite),
                    (prefix, suite)]:
                path = os.path.join(*names)
                if path not in paths:
                    try:
                        return self.load_passphrase_from_dir(path)
                    except (IOError, PassphraseError):
                        pass
                    paths.append(path)

        # 5/ Try SSH to remote host
        passphrase = self._load_passphrase_via_ssh(suite, owner, host)
        if passphrase:
            return passphrase

        if passphrase is None and cylc.flags.debug:
            print >> sys.stderr, (
                'ERROR: passphrase for suite %s not found for %s@%s' % (
                    suite, owner, host))

    @classmethod
    def load_passphrase_from_dir(cls, path):
        """Load passphrase from "passphrase" file under "path".

        Raise IOError if passphrase file does not exist.
        Raise PassphraseError if file content is bad.

        """
        # Create a new passphrase for the suite if necessary
        passphrase_file_name = os.path.join(path, cls.PASSPHRASE_FILE_BASE)
        passphrase = None
        for i, line in enumerate(open(passphrase_file_name)):
            # Check that it has 1 line with the correct number of characters
            if len(line) != cls.PASSPHRASE_LEN or i > 0:
                raise PassphraseError(passphrase_file_name)
            else:
                passphrase = line
        return passphrase

    def _load_passphrase_via_ssh(self, suite, owner, host):
        """Load passphrase from remote [owner@]host via SSH."""
        if not is_remote_host(host) and not is_remote_user(owner):
            return
        # Prefix STDOUT to ensure returned content is relevant
        prefix = r'[CYLC-PASSPHRASE] %(suite)s ' % {'suite': suite}
        # Extract suite definition directory from remote ~/.cylc/REGDB/SUITE
        # Attempt to cat passphrase file under suite definition directory
        script = (
            r'''echo -n '%(prefix)s'; '''
            r'''sed -n 's/^path=//p' '.cylc/REGDB/%(suite)s' | '''
            r'''xargs -I '{}' cat '{}/passphrase'; '''
            r'''echo'''
        ) % {'prefix': prefix, 'suite': suite}
        ssh_tmpl = str(GLOBAL_CFG.get_host_item(
            'remote shell template', host, owner))
        ssh_tmpl = ssh_tmpl.replace(' %s', '')  # back compat
        command = shlex.split(ssh_tmpl) + ['-n', owner + '@' + host, script]
        try:
            proc = Popen(command, stdout=PIPE, stderr=PIPE)
        except OSError:
            if cylc.flags.debug:
                traceback.print_exc()
            return
        out, err = proc.communicate()
        ret_code = proc.wait()
        # Extract passphrase from STDOUT
        # It should live in the line with the correct prefix
        passphrase = None
        for line in out.splitlines():
            if line.startswith(prefix):
                passphrase = line.replace(prefix, '').strip()
        if not passphrase or ret_code:
            if cylc.flags.debug:
                print >> sys.stderr, (
                    'ERROR: %(command)s # code=%(ret_code)s\n%(err)s\n'
                ) % {
                    'command': command,
                    # STDOUT may contain passphrase, so not safe to print
                    # 'out': out,
                    'err': err,
                    'ret_code': ret_code,
                }
            return
        return passphrase

    def register(self, name, path):
        """Register a suite, its source path and its title."""
        name = RegPath(name).get()
        for suite in self.list_all_suites():
            if name == suite:
                raise RegistrationError(
                    "ERROR: " + name + " is already registered.")
            elif suite.startswith(name + RegPath.delimiter):
                raise RegistrationError(
                    "ERROR: " + name + " is a registered group.")
            elif name.startswith(suite + RegPath.delimiter):
                # suite starts with, to some level, an existing suite name
                raise RegistrationError(
                    "ERROR: " + suite + " is a registered suite.")
        path = path.rstrip('/')  # strip trailing '/'
        path = re.sub('^\./', '', path)  # strip leading './'
        if not path.startswith('/'):
            # On AIX on GPFS os.path.abspath(path) returns the path with
            # full 'fileset' prefix. Manual use of $PWD to absolutize a
            # relative path gives a cleaner result.
            path = os.path.join(os.environ['PWD'], path)
        title = self.get_suite_title(name, path=path)
        title = title.split('\n')[0]  # use the first of multiple lines
        print 'REGISTER', name + ':', path
        self.dump_suite_data(name, {'path': path, 'title': title})

        # Create a new passphrase for the suite if necessary
        try:
            self.load_passphrase_from_dir(path)
        except (IOError, PassphraseError):
            self._dump_passphrase_to_dir(path)

    def get_suite_data(self, suite):
        """Return {"path": path, "title": title} a suite."""
        suite = RegPath(suite).get()
        fpath = os.path.join(self.dbpath, suite)
        if not os.path.isfile(fpath):
            raise RegistrationError("ERROR: Suite not found " + suite)
        data = {}
        with open(fpath, 'r') as handle:
            lines = handle.readlines()
        count = 0
        for line in lines:
            count += 1
            line = line.rstrip()
            try:
                key, val = line.split('=')
            except ValueError:
                print >> sys.stderr, (
                    'ERROR: failed to parse line ' + str(count) + ' from ' +
                    fpath + ':')
                print >> sys.stderr, '  ', line
                continue
            data[key] = val
        if 'title' not in data or 'path' not in data:
            raise RegistrationError(
                'ERROR, ' + suite + ' suite registration corrupted?: ' + fpath)
        return data

    def get_suitedir(self, reg):
        """Return the registered directory path of a suite."""
        data = self.get_suite_data(reg)
        return data['path']

    def get_suiterc(self, reg):
        """Return the suite.rc path of a suite."""
        data = self.get_suite_data(reg)
        return os.path.join(data['path'], 'suite.rc')

    def get_list(self, regfilter=None):
        """Return a filtered list of valid suite registrations."""
        res = []
        for suite in self.list_all_suites():
            if regfilter:
                try:
                    if not re.search(regfilter, suite):
                        continue
                except:
                    raise RegistrationError(
                        "ERROR, Invalid filter expression: " + regfilter)
            try:
                data = self.get_suite_data(suite)
            except RegistrationError as exc:
                print >> sys.stderr, str(exc)
            else:
                path, title = data['path'], data['title']
                res.append([suite, path, title])
        return res

    def unregister(self, exp):
        """Un-register a suite."""
        unregistered_set = set()
        skipped_set = set()
        ports_d = GLOBAL_CFG.get(['pyro', 'ports directory'])
        for name in sorted(self.list_all_suites()):
            if not re.match(exp + r'\Z', name):
                continue
            try:
                data = self.get_suite_data(name)
            except RegistrationError:
                continue
            if os.path.exists(os.path.join(ports_d, name)):
                skipped_set.add((name, data['path']))
                print >> sys.stderr, (
                    'SKIP UNREGISTER %s: port file exists' % (name))
                continue
            for base_name in ['passphrase', 'suite.rc.processed']:
                try:
                    os.unlink(os.path.join(data['path'], base_name))
                except OSError:
                    pass
            unregistered_set.add((name, data['path']))
            print 'UNREGISTER %s:%s' % (name, data['path'])
            os.unlink(os.path.join(self.dbpath, name))
        return unregistered_set, skipped_set

    def reregister(self, srce, targ):
        """Rename a source."""
        targ = RegPath(targ).get()
        found = False
        for suite in self.list_all_suites():
            if suite == srce:
                # single suite
                newsuite = targ
                data = self.get_suite_data(suite)
                self.unregister(suite)
                self.register(targ, data['path'])
                found = True
            elif suite.startswith(srce + RegPath.delimiter):
                # group of suites
                data = self.get_suite_data(suite)
                newsuite = re.sub('^' + srce, targ, suite)
                self.unregister(suite)
                self.register(newsuite, data['path'])
                found = True
        if not found:
            raise RegistrationError("ERROR, suite or group not found: " + srce)

    def get_invalid(self):
        """Return a list containing suite names that are no longer valid."""
        invalid = []
        for reg in self.list_all_suites():
            try:
                data = self.get_suite_data(reg)
            except RegistrationError:
                invalid.append(reg)
            else:
                rcfile = os.path.join(data['path'], 'suite.rc')
                if not os.path.isfile(rcfile):
                    invalid.append(reg)
        return invalid

    def get_suite_title(self, suite, path=None):
        """Determine the (first line of) the suite title without a full
        file parse. Assumes the title is not in an include-file."""

        if not path:
            data = self.get_suite_data(suite)
            path = data['path']
        suiterc = os.path.join(path, 'suite.rc')

        title = "No title provided"
        for line in open(suiterc, 'rb'):
            if re.search('^\s*\[', line):
                # abort: title comes before first [section]
                break
            match = re.match('^\s*title\s*=\s*(.*)\s*$', line)
            if match:
                line = match.groups()[0]
                title = line.strip('"\'')

        return title

    def refresh_suite_title(self, suite):
        """Update suite title, if necessary."""
        data = self.get_suite_data(suite)
        new_title = self.get_suite_title(suite)
        if data['title'] == new_title:
            if cylc.flags.verbose:
                print 'unchanged:', suite
            changed = False
        else:
            print 'RETITLED:', suite
            print '   old title:', data['title']
            print '   new title:', new_title
            changed = True
            data['title'] = new_title
            self.dump_suite_data(suite, data)
        return changed
