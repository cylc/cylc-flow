#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2015 NIWA
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
import sys
import re
import cylc.flags
from cylc.mkdir_p import mkdir_p
from cylc.regpath import RegPath
from cylc.passphrase import passphrase
from cylc.suite_host import get_hostname
from cylc.owner import user

REGDB_PATH = os.path.join(os.environ['HOME'], '.cylc', 'REGDB')


class RegistrationError(Exception):
    """Raise on suite registration error."""
    pass


class RegistrationDB(object):
    """Represents a simple suite name registration database."""

    Error = RegistrationError

    def __init__(self, dbpath=None):
        self.dbpath = dbpath or REGDB_PATH
        # create initial database directory if necessary
        if not os.path.exists(self.dbpath):
            try:
                mkdir_p(self.dbpath)
            except OSError as exc:
                sys.exit(str(exc))

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

    def register(self, name, path):
        """Register a suite, its source patha nd its title."""
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

        # create a new passphrase for the suite if necessary
        passphrase(name, user, get_hostname()).generate(path)

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
        suitedirs = []
        for key in self.list_all_suites():
            if re.search(exp + '$', key):
                try:
                    data = self.get_suite_data(key)
                except RegistrationError:
                    pass
                else:
                    path = data['path']
                    for base_name in ['passphrase', 'suite.rc.processed']:
                        try:
                            os.unlink(os.path.join(path, base_name))
                        except OSError:
                            pass
                    if path not in suitedirs:
                        # (could be multiple registrations of the same suite).
                        suitedirs.append(path)
                print 'UNREGISTER', key
                os.unlink(os.path.join(self.dbpath, key))
        return suitedirs

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
