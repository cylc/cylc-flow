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
"""Suite service files management."""

# Note: Some modules are NOT imported in the header. Expensive modules are only
# imported on demand.
import os
import re
from string import ascii_letters, digits
import sys

import cylc.flags
from cylc.mkdir_p import mkdir_p
from cylc.owner import USER, is_remote_user
from cylc.suite_host import get_hostname, is_remote_host, get_local_ip_address


class SuiteServiceFileError(Exception):
    """Raise on error related to suite service files."""
    pass


class SuiteSrvFilesManager(object):
    """Suite service files management."""

    DELIM = "/"
    DIR_BASE_AUTH = 'auth'
    DIR_BASE_SRV = ".cylc-var"
    FILE_BASE_CONTACT = "contact"
    FILE_BASE_PASSPHRASE = 'passphrase'
    FILE_BASE_SOURCE = "source"
    FILE_BASE_SSL_CERT = 'ssl.cert'
    FILE_BASE_SSL_PEM = 'ssl.pem'
    FILE_BASE_SUITE_RC = "suite.rc"
    KEY_HOST = "CYLC_SUITE_HOST"
    KEY_NAME = "CYLC_SUITE_NAME"
    KEY_OWNER = "CYLC_SUITE_OWNER"
    KEY_PORT = "CYLC_SUITE_PORT"
    KEY_VERSION = "CYLC_VERSION"
    PASSPHRASE_CHARSET = ascii_letters + digits
    PASSPHRASE_LEN = 20

    def __init__(self):
        self.local_passphrases = set()
        self.cache = {self.FILE_BASE_PASSPHRASE: {}}
        self.can_disk_cache_passphrases = {}
        self.can_use_load_auths = {}

    def cache_passphrase(self, reg, owner, host, value):
        """Cache and dump passphrase for a remote suite in standard location.

        Save passphrase to ~/.cylc/auth/owner@host/reg if possible.
        This is normally called on a successful authentication, and will cache
        the remote passphrase in memory as well.
        """
        if owner is None:
            owner = USER
        if host is None:
            host = get_hostname()
        path = self._get_cache_dir(reg, owner, host)
        self.cache[self.FILE_BASE_PASSPHRASE][(reg, owner, host)] = value
        # Dump to a file only for remote suites loaded via SSH.
        if self.can_disk_cache_passphrases.get((reg, owner, host)):
            # Although not desirable, failing to dump the passphrase to a file
            # is not disastrous.
            try:
                self._dump_item(path, self.FILE_BASE_PASSPHRASE, value)
            except (IOError, OSError):
                if cylc.flags.debug:
                    import traceback
                    traceback.print_exc()

    def dump_contact_file(self, reg, data):
        """Create contact file. Data should be a key=value dict."""
        with open(self.get_contact_file(reg), "wb") as handle:
            for key, value in sorted(data.items()):
                handle.write("%s=%s\n" % (key, value))

    def get_contact_file(self, reg):
        """Return name of contact file."""
        return os.path.join(
            self.get_suite_srv_dir(reg), self.FILE_BASE_CONTACT)

    def get_auth_item(self, item, reg, owner=None, host=None, content=False):
        """Locate/load passphrase, SSL private key, SSL certificate, etc.

        Return file name, or content of file if content=True is set.
        Files are searched from these locations in order:

        1/ For running task jobs, service directory under:
           a/ $CYLC_SUITE_RUN_DIR for remote jobs.
           b/ $CYLC_SUITE_RUN_DIR_ON_SUITE_HOST for local jobs or remote jobs
              with SSH messaging.

        2/ (Passphrases only) From memory cache, for remote suite passphrases.
           Don't use if content=False.

        3/ For suite on local user@host. The suite service directory.

        4/ Location under $HOME/.cylc/ for remote suite control from accounts
           that do not actually need the suite definition directory to be
           installed:
           $HOME/.cylc/auth/SUITE_OWNER@SUITE_HOST/SUITE_NAME/

        5/ For remote suites, try locating the file from the suite service
           directory on remote owner@host via SSH. If content=False, the value
           of the located file will be dumped under:
           $HOME/.cylc/auth/SUITE_OWNER@SUITE_HOST/SUITE_NAME/

        """
        if item not in [
                self.FILE_BASE_SSL_CERT, self.FILE_BASE_SSL_PEM,
                self.FILE_BASE_PASSPHRASE, self.FILE_BASE_CONTACT]:
            raise ValueError("%s: item not recognised" % item)
        if item == self.FILE_BASE_PASSPHRASE:
            self.can_disk_cache_passphrases[(reg, owner, host)] = False

        suite_host = os.getenv('CYLC_SUITE_HOST')
        suite_owner = os.getenv('CYLC_SUITE_OWNER')
        if reg == os.getenv('CYLC_SUITE_NAME'):
            env_keys = []
            if is_remote_host(suite_host) or is_remote_user(suite_owner):
                # 1(a)/ Task messaging call on a remote account.
                # Look in the remote suite run directory:
                env_keys = ['CYLC_SUITE_RUN_DIR']
            elif suite_host or suite_owner:
                # 1(b)/ Task messaging call on the suite host account.

                # Could be a local task or a remote task with 'ssh
                # messaging = True'. In either case use
                # $CYLC_SUITE_RUN_DIR_ON_SUITE_HOST which never changes.
                env_keys = ['CYLC_SUITE_RUN_DIR_ON_SUITE_HOST']
            for key in env_keys:
                path = os.path.join(os.environ[key], self.DIR_BASE_SRV)
                if content:
                    value = self._load_local_item(item, path)
                else:
                    value = self._locate_item(item, path)
                if value:
                    return value

        # 2/ From memory cache
        if item in self.cache:
            my_owner = owner
            my_host = host
            if my_owner is None:
                my_owner = USER
            if my_host is None:
                my_host = get_hostname()
            try:
                return self.cache[item][(reg, my_owner, my_host)]
            except KeyError:
                pass

        # 3/ Local suite service directory
        if self._is_local_auth_ok(reg, owner, host):
            path = self.get_suite_srv_dir(reg)
            if content:
                value = self._load_local_item(item, path)
            else:
                value = self._locate_item(item, path)
            if value:
                return value

        # 4/ Disk cache for remote suites
        if host is None:
            host = suite_host
        if owner is not None and host is not None:
            paths = [self._get_cache_dir(reg, owner, host)]
            short_host = host.split('.', 1)[0]
            if short_host != host:
                paths.append(self._get_cache_dir(reg, owner, short_host))
            for path in paths:
                if content:
                    value = self._load_local_item(item, path)
                else:
                    value = self._locate_item(item, path)
                if value:
                    return value

        # 5/ Use SSH to load content from remote owner@host
        value = self._load_remote_item(item, reg, owner, host)
        if value:
            if item == self.FILE_BASE_PASSPHRASE:
                self.can_disk_cache_passphrases[(reg, owner, host)] = True
            if not content:
                path = self._get_cache_dir(reg, owner, host)
                self._dump_item(path, item, value)
                value = os.path.join(path, item)
            return value

        raise SuiteServiceFileError("Couldn't get %s" % item)

    def get_suite_rc(self, reg, suite_owner=None):
        """Return the suite.rc path of a suite."""
        return os.path.join(
            self.get_suite_source_dir(reg, suite_owner),
            self.FILE_BASE_SUITE_RC)

    def get_suite_source_dir(self, reg, suite_owner=None):
        """Return the source directory path of a suite."""
        srv_d = self.get_suite_srv_dir(reg, suite_owner)
        fname = os.path.join(srv_d, self.FILE_BASE_SOURCE)
        try:
            source = os.readlink(fname)
        except OSError:
            raise SuiteServiceFileError("ERROR: Suite not found %s" % reg)
        else:
            if os.path.isabs(source):
                return source
            else:
                return os.path.normpath(os.path.join(srv_d, source))

    def get_suite_srv_dir(self, reg, suite_owner=None):
        """Return service directory of a suite."""
        if not suite_owner:
            suite_owner = USER
        run_d = os.getenv("CYLC_SUITE_RUN_DIR")
        if (not run_d or os.getenv("CYLC_SUITE_NAME") != reg or
                os.getenv("CYLC_SUITE_OWNER") != suite_owner):
            from cylc.cfgspec.globalcfg import GLOBAL_CFG
            run_d = GLOBAL_CFG.get_derived_host_item(
                reg, 'suite run directory')
        return os.path.join(run_d, self.DIR_BASE_SRV)

    def list_suites(self, regfilter=None):
        """Return a filtered list of valid suite registrations."""
        rec_regfilter = None
        if regfilter:
            try:
                rec_regfilter = re.compile(regfilter)
            except re.error as exc:
                raise ValueError("%s: %s" % (regfilter, exc))
        from cylc.cfgspec.globalcfg import GLOBAL_CFG
        run_d = GLOBAL_CFG.get_host_item('run directory')
        results = []
        skip_names = [
            "log", "share", "work", self.DIR_BASE_SRV, self.FILE_BASE_SUITE_RC]
        for dirpath, dnames, fnames in os.walk(run_d, followlinks=True):
            # Don't descent further if it looks like a suite directory
            if any([name in dnames or name in fnames for name in skip_names]):
                dnames[:] = []
            # Choose only suites with info file and matching filter
            reg = os.path.relpath(dirpath, run_d)
            path = os.path.join(dirpath, self.DIR_BASE_SRV)
            if (not self._locate_item(self.FILE_BASE_SOURCE, path) or
                    rec_regfilter and not rec_regfilter.search(reg)):
                continue
            try:
                results.append([
                    reg,
                    self.get_suite_source_dir(reg),
                    self._get_suite_title(reg)])
            except (IOError, SuiteServiceFileError) as exc:
                print >> sys.stderr, str(exc)
        return results

    def load_contact_file(self, reg, owner=None, host=None):
        """Load contact file. Return data as key=value dict."""
        file_content = self.get_auth_item(
            self.FILE_BASE_CONTACT, reg, owner, host, content=True)
        data = {}
        for line in file_content.splitlines():
            key, value = [item.strip() for item in line.split("=", 1)]
            data[key] = value
        return data

    def parse_suite_arg(self, options, arg):
        """From CLI arg "SUITE", return suite name and suite.rc path.

        If arg is a registered suite, suite name is the registered name.
        If arg is a directory, suite name is the base name of the
        directory.
        If arg is a file, suite name is the base name of its container
        directory.
        """
        try:
            path = self.get_suite_rc(arg, options.suite_owner)
            name = arg
        except SuiteServiceFileError:
            arg = os.path.abspath(arg)
            if os.path.isdir(arg):
                path = os.path.join(arg, self.FILE_BASE_SUITE_RC)
                name = os.path.basename(arg)
            else:
                path = arg
                name = os.path.basename(os.path.dirname(arg))
        return name, path

    def register(self, reg, source=None):
        """Generate service files for a suite. Record its source location."""
        srv_d = self.get_suite_srv_dir(reg)
        target = os.path.join(srv_d, self.FILE_BASE_SOURCE)
        if source is None:
            try:
                # No change if already registered
                source_str = os.readlink(target)
            except OSError:
                # Source path is assumed to be the run directory
                source_str = ".."
        else:
            # Tidy source path
            if os.path.basename(source) == self.FILE_BASE_SUITE_RC:
                source = os.path.dirname(source)
            if not os.path.isabs(source):
                # On AIX on GPFS os.path.abspath(source) returns the source
                # with full 'fileset' prefix. Manual use of $PWD to absolutize
                # a relative path gives a cleaner result.
                source = os.path.join(os.getenv("PWD", os.getcwd()), source)
            source = os.path.normpath(source)
            if (os.path.abspath(source) ==
                    os.path.abspath(os.path.dirname(srv_d))):
                source_str = ".."
            else:
                source_str = source
        # Create target if it does not exist.
        # Re-create target if it does not point to specified source.
        mkdir_p(srv_d)
        try:
            orig_source_str = os.readlink(target)
        except OSError:
            os.symlink(source_str, target)
        else:
            if orig_source_str != source_str:
                os.unlink(target)
                os.symlink(source_str, target)

        # Create a new passphrase for the suite if necessary.
        if not self._locate_item(self.FILE_BASE_PASSPHRASE, srv_d):
            import random
            self._dump_item(srv_d, self.FILE_BASE_PASSPHRASE, ''.join(
                random.sample(self.PASSPHRASE_CHARSET, self.PASSPHRASE_LEN)))

        # Create a new certificate/private key for the suite if necessary.
        if not (self._locate_item(self.FILE_BASE_SSL_PEM, srv_d) and
                self._locate_item(self.FILE_BASE_SSL_CERT, srv_d)):
            self._create_ssl_pem_and_cert(srv_d, reg)

    def _create_ssl_pem_and_cert(self, path, reg):
        """Create ssl.pem and ssl.cert files for suite in path."""
        try:
            from OpenSSL import crypto
        except ImportError:
            # OpenSSL not installed, so we can't use HTTPS anyway.
            return
        host = get_hostname()
        altnames = [
            "DNS:*", "DNS:%s" % host,
            "IP:%s" % get_local_ip_address(host),
            # See https://github.com/kennethreitz/requests/issues/2621
            "DNS:%s" % get_local_ip_address(host)]

        # Use suite name as the 'common name', but no more than 64 chars.
        cert_common_name = reg
        if len(reg) > 64:
            cert_common_name = reg[:61] + "..."

        # Create a private key.
        pkey_obj = crypto.PKey()
        pkey_obj.generate_key(crypto.TYPE_RSA, 2048)
        self._dump_item(
            path, self.FILE_BASE_SSL_PEM,
            crypto.dump_privatekey(crypto.FILETYPE_PEM, pkey_obj))

        # Create a self-signed certificate.
        cert_obj = crypto.X509()
        cert_obj.get_subject().O = "Cylc"
        cert_obj.get_subject().CN = cert_common_name
        cert_obj.gmtime_adj_notBefore(0)
        cert_obj.gmtime_adj_notAfter(10 * 365 * 24 * 60 * 60)  # 10 years.
        cert_obj.set_issuer(cert_obj.get_subject())
        cert_obj.set_pubkey(pkey_obj)
        cert_obj.add_extensions([crypto.X509Extension(
            "subjectAltName", False, ", ".join(altnames))])
        cert_obj.sign(pkey_obj, 'sha256')
        self._dump_item(
            path, self.FILE_BASE_SSL_CERT,
            crypto.dump_certificate(crypto.FILETYPE_PEM, cert_obj))

    def _dump_item(self, path, item, value):
        """Dump "value" to a file called "item" in the directory "path".

        1. File permission should already be user-read-write-only on
           creation by mkstemp.
        2. The combination of os.fsync and os.rename should guarentee
           that we don't end up with an incomplete file.
        """
        mkdir_p(path)
        from tempfile import NamedTemporaryFile
        handle = NamedTemporaryFile(prefix=item, dir=path, delete=False)
        handle.write(value)
        os.fsync(handle.fileno())
        handle.close()
        fname = os.path.join(path, item)
        os.rename(handle.name, fname)
        if cylc.flags.verbose:
            print 'Generated %s' % fname

    def _get_cache_dir(self, reg, owner, host):
        """Return the cache directory for remote suite service files."""
        return os.path.join(
            os.path.expanduser("~"), ".cylc", self.DIR_BASE_AUTH,
            "%s@%s" % (owner, host), reg)

    def _get_suite_title(self, reg):
        """Return the the suite title without a full file parse

        Limitations:
        * 1st line of title only.
        * Assume title is not in an include-file.
        """
        title = "No title provided"
        for line in open(self.get_suite_rc(reg), 'rb'):
            if line.lstrip().startswith("["):
                # abort: title comes before first [section]
                break
            match = re.match('^\s*title\s*=\s*(.*)\s*$', line)
            if match:
                title = match.groups()[0].strip('"\'')
        return title

    def _is_local_auth_ok(self, reg, owner, host):
        """Return True if it is OK to use local passphrase, ssl.* files.

        Use values in ~/cylc-run/REG/.cylc-var/contact to make a judgement.
        Cache results in self.can_use_load_auths.
        """
        if (reg, owner, host) not in self.can_use_load_auths:
            if is_remote_user(owner) or is_remote_host(host):
                fname = os.path.join(
                    self.get_suite_srv_dir(reg), self.FILE_BASE_CONTACT)
                data = {}
                try:
                    for line in open(fname):
                        key, value = (
                            [item.strip() for item in line.split("=", 1)])
                        data[key] = value
                except IOError, ValueError:
                    # No contact file
                    self.can_use_load_auths[(reg, owner, host)] = False
                else:
                    # Contact file exists, check values match
                    if owner is None:
                        owner = USER
                    if host is None:
                        host = get_hostname()
                    host_value = data.get(self.KEY_HOST, "")
                    self.can_use_load_auths[(reg, owner, host)] = (
                        reg == data.get(self.KEY_NAME) and
                        owner == data.get(self.KEY_OWNER) and
                        (
                            host == host_value or
                            host == host_value.split(".", 1)[0]  # no domain
                        )
                    )
            else:
                self.can_use_load_auths[(reg, owner, host)] = True
        return self.can_use_load_auths[(reg, owner, host)]

    @staticmethod
    def _load_local_item(item, path):
        """Load and return content of a file (item) in path."""
        try:
            return open(os.path.join(path, item)).read()
        except IOError:
            return None

    def _load_remote_item(self, item, reg, owner, host):
        """Load content of service item from remote [owner@]host via SSH."""
        if not is_remote_host(host) and not is_remote_user(owner):
            return
        # Prefix STDOUT to ensure returned content is relevant
        prefix = r'[CYLC-AUTH] %(suite)s' % {'suite': reg}
        # Attempt to cat passphrase file under suite service directory
        from cylc.cfgspec.globalcfg import GLOBAL_CFG
        script = (
            r"""echo '%(prefix)s'; """
            r'''cat "%(run_d)s/%(srv_base)s/%(item)s"'''
        ) % {
            'prefix': prefix,
            'run_d': GLOBAL_CFG.get_derived_host_item(
                reg, 'suite run directory', host, owner),
            'srv_base': self.DIR_BASE_SRV,
            'item': item
        }
        import shlex
        command = shlex.split(
            GLOBAL_CFG.get_host_item('remote shell template', host, owner))
        command += ['-n', owner + '@' + host, script]
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
        content = ""
        can_read = False
        for line in out.splitlines(True):
            if can_read:
                content += line
            elif line.strip() == prefix:
                can_read = True
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
        return content

    @staticmethod
    def _locate_item(item, path):
        """Locate a service item in "path"."""
        fname = os.path.join(path, item)
        if os.path.exists(fname):
            return fname
