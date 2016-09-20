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
import re
from string import ascii_letters, digits
import sys

import cylc.flags
from cylc.mkdir_p import mkdir_p
from cylc.owner import USER, is_remote_user
from cylc.regpath import RegPath
from cylc.suite_host import get_hostname, is_remote_host, get_local_ip_address

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
    SSL_CERTIFICATE_FILE_BASE = 'ssl.cert'
    SSL_PRIVATE_KEY_FILE_BASE = 'ssl.pem'

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
        self.can_disk_cache_passphrases = {}

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
        # Dump to a file only for remote suites loaded via SSH.
        if self.can_disk_cache_passphrases.get((suite, owner, host)):
            # Although not desirable, failing to dump the passphrase to a file
            # is not disastrous.
            try:
                self._dump_passphrase_to_dir(path, passphrase)
            except (IOError, OSError):
                if cylc.flags.debug:
                    import traceback
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
        from tempfile import NamedTemporaryFile
        handle = NamedTemporaryFile(
            prefix=self.PASSPHRASE_FILE_BASE, dir=path, delete=False)
        # Note: Perhaps a UUID might be better here?
        if passphrase is None:
            import random
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

    def _dump_certificate_and_key_to_dir(self, path, suite):
        """Dump SSL certificate to "ssl.cert" file in "path"."""
        try:
            from OpenSSL import crypto
        except ImportError:
            # OpenSSL not installed, so we can't use HTTPS anyway.
            return
        host = get_hostname()
        altnames = ["DNS:*", "DNS:%s" % host,
                    "IP:%s" % get_local_ip_address(host)]
        # Workaround for https://github.com/kennethreitz/requests/issues/2621
        altnames.append("DNS:%s" % get_local_ip_address(host))

        # Use suite name as the 'common name', but no more than 64 chars.
        cert_common_name = suite
        if len(suite) > 64:
            cert_common_name = suite[:61] + "..."

        # Create a private key.
        pkey_obj = crypto.PKey()
        pkey_obj.generate_key(crypto.TYPE_RSA, 2048)

        # Create a self-signed certificate.
        cert_obj = crypto.X509()
        cert_obj.get_subject().O = "Cylc"
        cert_obj.get_subject().CN = cert_common_name
        cert_obj.gmtime_adj_notBefore(0)
        cert_obj.gmtime_adj_notAfter(10 * 365 * 24 * 60 * 60)  # 10 years.
        cert_obj.set_issuer(cert_obj.get_subject())
        cert_obj.set_pubkey(pkey_obj)
        cert_obj.add_extensions([
            crypto.X509Extension(
                "subjectAltName", False, ", ".join(altnames)
            )
        ])
        cert_obj.sign(pkey_obj, 'sha256')

        mkdir_p(path)

        # Work in a user-read-write-only directory for guaranteed safety.
        from tempfile import mkdtemp
        work_dir = mkdtemp()
        pkey_file = os.path.join(work_dir, self.SSL_PRIVATE_KEY_FILE_BASE)
        cert_file = os.path.join(work_dir, self.SSL_CERTIFICATE_FILE_BASE)

        with open(pkey_file, "w") as file_handle:
            file_handle.write(
                crypto.dump_privatekey(crypto.FILETYPE_PEM, pkey_obj))
        with open(cert_file, "w") as file_handle:
            file_handle.write(
                crypto.dump_certificate(crypto.FILETYPE_PEM, cert_obj))

        import stat
        os.chmod(pkey_file, stat.S_IRUSR)
        os.chmod(cert_file, stat.S_IRUSR)
        pkey_dest_file = os.path.join(path, self.SSL_PRIVATE_KEY_FILE_BASE)
        cert_dest_file = os.path.join(path, self.SSL_CERTIFICATE_FILE_BASE)
        import shutil
        shutil.copy(pkey_file, pkey_dest_file)
        shutil.copy(cert_file, cert_dest_file)
        shutil.rmtree(work_dir)
        if cylc.flags.verbose:
            print 'Generated suite SSL certificate: %s' % cert_dest_file
            print 'Generated suite SSL private key: %s' % pkey_dest_file

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
                    import traceback
                    traceback.print_exc()

        # Find all passphrases installed under ~/.cylc/
        for items in os.walk(os.path.expanduser('~/.cylc')):
            # items = dirpath, dirnames, filenames
            try:
                self.local_passphrases.add(
                    self.load_passphrase_from_dir(items[0]))
            except (IOError, PassphraseError):
                if cylc.flags.debug:
                    import traceback
                    traceback.print_exc()

        return self.local_passphrases

    def load_item_from_dir(self, path, item):
        if item == "passphrase":
            return self.load_passphrase_from_dir(path)
        file_name = os.path.join(path, item)
        try:
            content = open(file_name).read()
        except IOError:
            raise
        if not content:
            raise PassphraseError("no content in %s" % file_name)
        return file_name

    def load_passphrase(self, suite, owner, host, cache_ok=True):
        """Search for passphrase file for suite, load and return content."""
        return self.load_item(suite, owner, host, item="passphrase",
                              cache_ok=cache_ok)

    def load_item(self, suite, owner, host, item="certificate",
                  create_ok=False, cache_ok=False):
        """Load or create a passphrase, SSL certificate or a private key.

        SSL files are searched from these locations in order:

        1/ For running task jobs:
           a/ $CYLC_SUITE_RUN_DIR then $CYLC_SUITE_DEF_PATH for remote jobs.
           b/ $CYLC_SUITE_DEF_PATH_ON_SUITE_HOST for local jobs or remote jobs
              with SSH messaging.

        2/ (Passphrases only) From memory cache, for remote suite passphrases.
           Don't use if cache_ok=False.

        3/ For suite on local user@host. The suite definition directory, as
           registered. (Note: Previously, this needs to be the 1st location,
           else sub-suites load their parent suite's passphrases, etc, on
           start-up because the "cylc run" command runs in a parent suite task
           execution environment. This problem no longer exists becase on suite
           start up, the "load_item_from_dir" method is called directly
           instead of through this method.)

        4/ Location under $HOME/.cylc/ for remote suite control from accounts
           that do not actually need the suite definition directory to be
           installed:
           $HOME/.cylc/passphrases/SUITE_OWNER@SUITE_HOST/SUITE_NAME/

        5/ (SSL files only) If create_ok is specified, create the SSL file and
           then return it.

        6/ For remote suites, try locating the file from the suite definition
           directory on remote owner@host via SSH.

        """
        item_is_passphrase = False
        if item == "certificate":
            item = self.SSL_CERTIFICATE_FILE_BASE
        elif item == "private_key":
            item = self.SSL_PRIVATE_KEY_FILE_BASE
        elif item == "passphrase":
            item_is_passphrase = True
            self.can_disk_cache_passphrases[(suite, owner, host)] = False

        suite_host = os.getenv('CYLC_SUITE_HOST')
        suite_owner = os.getenv('CYLC_SUITE_OWNER')
        if suite == os.getenv('CYLC_SUITE_NAME'):
            env_keys = []
            if is_remote_host(suite_host) or is_remote_user(suite_owner):
                # 1(a)/ Task messaging call on a remote account.
                # First look in the remote suite run directory than suite
                # definition directory ($CYLC_SUITE_DEF_PATH is modified
                # for remote tasks):
                env_keys = ['CYLC_SUITE_RUN_DIR', 'CYLC_SUITE_DEF_PATH']
            elif suite_host or suite_owner:
                # 1(b)/ Task messaging call on the suite host account.

                # Could be a local task or a remote task with 'ssh
                # messaging = True'. In either case use
                # $CYLC_SUITE_DEF_PATH_ON_SUITE_HOST which never
                # changes, not $CYLC_SUITE_DEF_PATH which gets
                # modified for remote tasks as described above.
                env_keys = ['CYLC_SUITE_DEF_PATH_ON_SUITE_HOST']
            for key in env_keys:
                try:
                    return self.load_item_from_dir(os.environ[key], item)
                except (KeyError, IOError, PassphraseError):
                    pass

        # 2/ From memory cache
        if cache_ok and item_is_passphrase:
            pass_owner = owner
            pass_host = host
            if pass_owner is None:
                pass_owner = USER
            if pass_host is None:
                pass_host = get_hostname()
            try:
                return self.cached_passphrases[(suite, pass_owner, pass_host)]
            except KeyError:
                pass

        # 3/ Cylc commands with suite definition directory from local reg.
        if cache_ok or not is_remote_user(owner) and not is_remote_host(host):
            try:
                return self.load_item_from_dir(self.get_suitedir(suite), item)
            except (IOError, PassphraseError, RegistrationError):
                pass

        # 4/ Other allowed locations, as documented above.
        prefix = os.path.expanduser(os.path.join('~', '.cylc'))
        if host is None:
            host = suite_host
        if (owner is not None and host is not None and
                (not item_is_passphrase or cache_ok)):
            prefix = os.path.expanduser(os.path.join('~', '.cylc'))
            paths = []
            path_types = [(prefix, self.PASSPHRASES_DIR_BASE,
                           owner + "@" + host, suite)]
            short_host = host.split('.', 1)[0]
            if short_host != host:
                path_types.append((prefix, self.PASSPHRASES_DIR_BASE,
                                  owner + "@" + short_host, suite))

            for names in path_types:
                try:
                    return self.load_item_from_dir(os.path.join(*names), item)
                except (IOError, PassphraseError):
                    pass

        if create_ok and not item_is_passphrase:
            # 5/ Create the SSL file if it doesn't exist.
            return self._dump_certificate_and_key_to_dir(
                self.get_suitedir(suite), suite)

        load_dest_root = None
        if not item_is_passphrase:
            load_dest_root = os.path.join(
                prefix, self.PASSPHRASES_DIR_BASE, owner + "@" + host, suite)
        try:
            # 6/ Try ssh-ing to grab the files directly.
            content = self._load_item_via_ssh(
                item, suite, owner, host, dest_dir=load_dest_root)
            if content and item_is_passphrase:
                self.can_disk_cache_passphrases[(suite, owner, host)] = True
            return content
        except Exception as exc:
            import traceback
            traceback.print_exc()
        raise PassphraseError("Couldn't get %s" % item)

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
        return self._load_item_via_ssh(
            self.PASSPHRASE_FILE_BASE, suite, owner, host)

    def _load_item_via_ssh(self, item, suite, owner, host, dest_dir=None):
        """Load item (e.g. passphrase) from remote [owner@]host via SSH."""
        if not is_remote_host(host) and not is_remote_user(owner):
            return
        # Prefix STDOUT to ensure returned content is relevant
        prefix = r'[CYLC-PASSPHRASE] %(suite)s ' % {'suite': suite}
        # Extract suite definition directory from remote ~/.cylc/REGDB/SUITE
        # Attempt to cat passphrase file under suite definition directory
        script = (
            r'''echo -n '%(prefix)s'; '''
            r'''sed -n 's/^path=//p' '.cylc/REGDB/%(suite)s' | '''
            r'''xargs -I '{}' cat '{}/%(item)s'; '''
            r'''echo'''
        ) % {'prefix': prefix, 'suite': suite, 'item': item}
        from cylc.cfgspec.globalcfg import GLOBAL_CFG
        ssh_tmpl = str(GLOBAL_CFG.get_host_item(
            'remote shell template', host, owner))
        ssh_tmpl = ssh_tmpl.replace(' %s', '')  # back compat
        import shlex
        command = shlex.split(ssh_tmpl) + ['-n', owner + '@' + host, script]
        from subprocess import Popen, PIPE
        try:
            proc = Popen(command, stdout=PIPE, stderr=PIPE)
        except OSError:
            if cylc.flags.debug:
                import traceback
                traceback.print_exc()
            return
        out, err = proc.communicate()
        ret_code = proc.wait()
        # Extract passphrase from STDOUT
        # It should live in the line with the correct prefix
        if item == self.PASSPHRASE_FILE_BASE:
            content = None
            for line in out.splitlines():
                if line.startswith(prefix):
                    content = line.replace(prefix, '').strip()
        else:
            content = []
            content_has_started = False
            for line in out.splitlines():
                if line.startswith(prefix):
                    line = line.replace(prefix, '')
                    content_has_started = True
                if content_has_started:
                    content.append(line)
            content = "\n".join(content)
        if not content or ret_code:
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
        if dest_dir is not None:
            if not os.path.exists(dest_dir):
                os.makedirs(dest_dir)
            os.chmod(dest_dir, 0700)
            dest_item = os.path.join(dest_dir, item)
            file_handle = open(dest_item, "w")
            file_handle.write(content)
            file_handle.close()
            os.chmod(dest_item, 0600)
            return dest_item
        return content

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

        # Create a new passphrase for the suite if necessary.
        try:
            self.load_item_from_dir(path, "passphrase")
        except (IOError, PassphraseError):
            self._dump_passphrase_to_dir(path)

        # Create a new certificate/private key for the suite if necessary.
        try:
            self.load_item_from_dir(path, self.SSL_PRIVATE_KEY_FILE_BASE)
            self.load_item_from_dir(path, self.SSL_CERTIFICATE_FILE_BASE)
        except (IOError, PassphraseError):
            self._dump_certificate_and_key_to_dir(path, name)

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
        from cylc.cfgspec.globalcfg import GLOBAL_CFG
        ports_d = GLOBAL_CFG.get(['communication', 'ports directory'])
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
            for base_name in ['passphrase', 'suite.rc.processed',
                              self.SSL_CERTIFICATE_FILE_BASE,
                              self.SSL_PRIVATE_KEY_FILE_BASE]:
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
