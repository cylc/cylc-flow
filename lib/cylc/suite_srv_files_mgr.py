#!/usr/bin/env python3

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
"""Suite service files management."""

# Note: Some modules are NOT imported in the header. Expensive modules are only
# imported on demand.
import os
import re
from string import ascii_letters, digits

from cylc import LOG
from cylc.cfgspec.glbl_cfg import glbl_cfg
from cylc.exceptions import SuiteServiceFileError
import cylc.flags
from cylc.hostuserutil import (
    get_host, get_user, is_remote, is_remote_host, is_remote_user)


class SuiteSrvFilesManager(object):
    """Suite service files management."""

    DELIM = "/"
    DIR_BASE_AUTH = "auth"
    DIR_BASE_SRV = ".service"
    FILE_BASE_CONTACT = "contact"
    FILE_BASE_CONTACT2 = "contact2"
    FILE_BASE_PASSPHRASE = "passphrase"
    FILE_BASE_SOURCE = "source"
    FILE_BASE_SUITE_RC = "suite.rc"
    KEY_API = "CYLC_API"
    KEY_COMMS_PROTOCOL_2 = "CYLC_COMMS_PROTOCOL_2"  # indirect comms
    KEY_DIR_ON_SUITE_HOST = "CYLC_DIR_ON_SUITE_HOST"
    KEY_HOST = "CYLC_SUITE_HOST"
    KEY_NAME = "CYLC_SUITE_NAME"
    KEY_OWNER = "CYLC_SUITE_OWNER"
    KEY_PROCESS = "CYLC_SUITE_PROCESS"
    KEY_PORT = "CYLC_SUITE_PORT"
    KEY_SSH_USE_LOGIN_SHELL = "CYLC_SSH_USE_LOGIN_SHELL"
    KEY_SUITE_RUN_DIR_ON_SUITE_HOST = "CYLC_SUITE_RUN_DIR_ON_SUITE_HOST"
    KEY_TASK_MSG_MAX_TRIES = "CYLC_TASK_MSG_MAX_TRIES"
    KEY_TASK_MSG_RETRY_INTVL = "CYLC_TASK_MSG_RETRY_INTVL"
    KEY_TASK_MSG_TIMEOUT = "CYLC_TASK_MSG_TIMEOUT"
    KEY_UUID = "CYLC_SUITE_UUID"
    KEY_VERSION = "CYLC_VERSION"
    NO_TITLE = "No title provided"
    PASSPHRASE_CHARSET = ascii_letters + digits
    PASSPHRASE_LEN = 20
    PS_OPTS = '-opid,args'
    REC_TITLE = re.compile(r"^\s*title\s*=\s*(.*)\s*$")

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
            owner = get_user()
        if host is None:
            host = get_host()
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

    def detect_old_contact_file(self, reg, check_host_port=None):
        """Detect old suite contact file.

        If an old contact file does not exist, do nothing. If one does exist
        but the suite process is definitely not alive, remove it. If one exists
        and the suite process is still alive, raise SuiteServiceFileError.

        If check_host_port is specified and does not match the (host, port)
        value in the old contact file, raise AssertionError.

        Args:
            reg (str): suite name
            check_host_port (tuple): (host, port) to check against

        Raise:
            AssertionError:
                If old contact file exists but does not have matching
                (host, port) with value of check_host_port.
            SuiteServiceFileError:
                If old contact file exists and the suite process still alive.
        """
        # An old suite of the same name may be running if a contact file exists
        # and can be loaded.
        try:
            data = self.load_contact_file(reg)
            old_host = data[self.KEY_HOST]
            old_port = data[self.KEY_PORT]
            old_proc_str = data[self.KEY_PROCESS]
        except (IOError, ValueError, SuiteServiceFileError):
            # Contact file does not exist or corrupted, should be OK to proceed
            return
        if check_host_port and check_host_port != (old_host, int(old_port)):
            raise AssertionError("%s != (%s, %s)" % (
                check_host_port, old_host, old_port))
        # Run the "ps" command to see if the process is still running or not.
        # If the old suite process is still running, it should show up with the
        # same command line as before.
        # Terminate command after 10 seconds to prevent hanging, etc.
        old_pid_str = old_proc_str.split(None, 1)[0].strip()
        cmd = ["timeout", "10", "ps", self.PS_OPTS, str(old_pid_str)]
        if is_remote_host(old_host):
            import shlex
            ssh_str = str(glbl_cfg().get_host_item("ssh command", old_host))
            cmd = shlex.split(ssh_str) + ["-n", old_host] + cmd
        from subprocess import Popen, PIPE
        from time import sleep, time
        proc = Popen(cmd, stdin=open(os.devnull), stdout=PIPE, stderr=PIPE)
        # Terminate command after 10 seconds to prevent hanging SSH, etc.
        timeout = time() + 10.0
        while proc.poll() is None:
            if time() > timeout:
                proc.terminate()
            sleep(0.1)
        fname = self.get_contact_file(reg)
        ret_code = proc.wait()
        out, err = (f.decode() for f in proc.communicate())
        if ret_code:
            LOG.debug("$ %s  # return %d\n%s", ' '.join(cmd), ret_code, err)
        for line in reversed(out.splitlines()):
            if line.strip() == old_proc_str:
                # Suite definitely still running
                break
            elif line.split(None, 1)[0].strip() == "PID":
                # Only "ps" header - "ps" has run, but no matching results.
                # Suite not running. Attempt to remove suite contact file.
                try:
                    os.unlink(fname)
                    return
                except OSError:
                    break

        raise SuiteServiceFileError(
            (
                r"""suite contact file exists: %(fname)s

Suite "%(suite)s" is already running, and listening at "%(host)s:%(port)s".

To start a new run, stop the old one first with one or more of these:
* cylc stop %(suite)s              # wait for active tasks/event handlers
* cylc stop --kill %(suite)s       # kill active tasks and wait
* cylc stop --now %(suite)s        # don't wait for active tasks
* cylc stop --now --now %(suite)s  # don't wait
* ssh -n "%(host)s" kill %(pid)s   # final brute force!
"""
            ) % {
                "host": old_host,
                "port": old_port,
                "pid": old_pid_str,
                "fname": fname,
                "suite": reg,
            }
        )

    def dump_contact_file(self, reg, data):
        """Create contact file. Data should be a key=value dict."""
        # Note:
        # 1st fsync for writing the content of the contact file to disk.
        # 2nd fsync for writing the file metadata of the contact file to disk.
        # The double fsync logic ensures that if the contact file is written to
        # a shared file system e.g. via NFS, it will be immediately visible
        # from by a process on other hosts after the current process returns.
        with open(self.get_contact_file(reg), "wb") as handle:
            for key, value in sorted(data.items()):
                handle.write(("%s=%s\n" % (key, value)).encode())
            os.fsync(handle.fileno())
        dir_fileno = os.open(self.get_suite_srv_dir(reg), os.O_DIRECTORY)
        os.fsync(dir_fileno)
        os.close(dir_fileno)

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
                self.FILE_BASE_PASSPHRASE, self.FILE_BASE_CONTACT,
                self.FILE_BASE_CONTACT2]:
            raise ValueError("%s: item not recognised" % item)
        if item == self.FILE_BASE_PASSPHRASE:
            self.can_disk_cache_passphrases[(reg, owner, host)] = False

        if reg == os.getenv('CYLC_SUITE_NAME'):
            env_keys = []
            if 'CYLC_SUITE_RUN_DIR' in os.environ:
                # 1(a)/ Task messaging call.
                env_keys.append('CYLC_SUITE_RUN_DIR')
            elif self.KEY_SUITE_RUN_DIR_ON_SUITE_HOST in os.environ:
                # 1(b)/ Task messaging call via ssh messaging.
                env_keys.append(self.KEY_SUITE_RUN_DIR_ON_SUITE_HOST)
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
                my_owner = get_user()
            if my_host is None:
                my_host = get_host()
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
        # Note: It is not possible to find ".service/contact2" on the suite
        # host, because it is installed on task host by "cylc remote-init" on
        # demand.
        if item != self.FILE_BASE_CONTACT2:
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
        """Return the source directory path of a suite.

        Will register un-registered suites located in the cylc run dir.
        """
        srv_d = self.get_suite_srv_dir(reg, suite_owner)
        fname = os.path.join(srv_d, self.FILE_BASE_SOURCE)
        try:
            source = os.readlink(fname)
        except OSError:
            suite_d = os.path.dirname(srv_d)
            if os.path.exists(suite_d) and not is_remote_user(suite_owner):
                # suite exists but is not yet registered
                self.register(reg=reg, source=suite_d)
                return suite_d
            else:
                raise SuiteServiceFileError("Suite not found %s" % reg)
        else:
            if os.path.isabs(source):
                return source
            else:
                return os.path.normpath(os.path.join(srv_d, source))

    def get_suite_srv_dir(self, reg, suite_owner=None):
        """Return service directory of a suite."""
        if not suite_owner:
            suite_owner = get_user()
        run_d = os.getenv("CYLC_SUITE_RUN_DIR")
        if (not run_d or os.getenv("CYLC_SUITE_NAME") != reg or
                os.getenv("CYLC_SUITE_OWNER") != suite_owner):
            run_d = glbl_cfg().get_derived_host_item(
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
        run_d = glbl_cfg().get_host_item('run directory')
        results = []
        for dirpath, dnames, _ in os.walk(run_d, followlinks=True):
            # Always descend for top directory, but
            # don't descend further if it has a .service/ dir
            if dirpath != run_d and self.DIR_BASE_SRV in dnames:
                dnames[:] = []
            # Choose only suites with .service and matching filter
            reg = os.path.relpath(dirpath, run_d)
            path = os.path.join(dirpath, self.DIR_BASE_SRV)
            if (not self._locate_item(self.FILE_BASE_SOURCE, path) or
                    rec_regfilter and not rec_regfilter.search(reg)):
                continue
            try:
                results.append([
                    reg,
                    self.get_suite_source_dir(reg),
                    self.get_suite_title(reg)])
            except (IOError, SuiteServiceFileError) as exc:
                LOG.error('%s: %s', reg, exc)
        return results

    def load_contact_file(self, reg, owner=None, host=None, file_base=None):
        """Load contact file. Return data as key=value dict."""
        if not file_base:
            file_base = self.FILE_BASE_CONTACT
        file_content = self.get_auth_item(
            file_base, reg, owner, host, content=True)
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
        if arg == '.':
            arg = os.getcwd()
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

    def register(self, reg=None, source=None, redirect=False):
        """Register a suite, or renew its registration.

        Create suite service directory and symlink to suite source location.

        Args:
            reg (str): suite name, default basename($PWD).
            source (str): directory location of suite.rc file, default $PWD.
            redirect (bool): allow reuse of existing name and run directory.

        Return:
            The registered suite name (which may be computed here).

        Raise:
            SuiteServiceFileError:
                No suite.rc file found in source location.
                Illegal name (can look like a relative path, but not absolute).
                Another suite already has this name (unless --redirect).
        """
        if reg is None:
            reg = os.path.basename(os.getcwd())

        if os.path.isabs(reg):
            raise SuiteServiceFileError(
                "suite name cannot be an absolute path: %s" % reg)

        if source is not None:
            if os.path.basename(source) == self.FILE_BASE_SUITE_RC:
                source = os.path.dirname(source)
        else:
            source = os.getcwd()

        # suite.rc must exist so we can detect accidentally reversed args.
        source = os.path.abspath(source)
        if not os.path.isfile(os.path.join(source, self.FILE_BASE_SUITE_RC)):
            raise SuiteServiceFileError("no suite.rc in %s" % source)

        # Create service dir if necessary.
        srv_d = self.get_suite_srv_dir(reg)
        os.makedirs(srv_d, exist_ok=True)

        # See if suite already has a source or not
        try:
            orig_source = os.readlink(
                os.path.join(srv_d, self.FILE_BASE_SOURCE))
        except OSError:
            orig_source = None
        else:
            if not os.path.isabs(orig_source):
                orig_source = os.path.normpath(
                    os.path.join(srv_d, orig_source))
        if orig_source is not None and source != orig_source:
            if not redirect:
                raise SuiteServiceFileError(
                    "the name '%s' already points to %s.\nUse "
                    "--redirect to re-use an existing name and run "
                    "directory." % (reg, orig_source))
            LOG.warning(
                "the name '%(reg)s' points to %(old)s.\nIt will now"
                " be redirected to %(new)s.\nFiles in the existing %(reg)s run"
                " directory will be overwritten.\n",
                {'reg': reg, 'old': orig_source, 'new': source})
            # Remove symlink to the original suite.
            os.unlink(os.path.join(srv_d, self.FILE_BASE_SOURCE))

        # Create symlink to the suite, if it doesn't already exist.
        if orig_source is None or source != orig_source:
            target = os.path.join(srv_d, self.FILE_BASE_SOURCE)
            if (os.path.abspath(source) ==
                    os.path.abspath(os.path.dirname(srv_d))):
                # If source happens to be the run directory,
                # create .service/source -> ..
                source_str = ".."
            else:
                source_str = source
            os.symlink(source_str, target)

        print('REGISTERED %s -> %s' % (reg, source))
        return reg

    def create_auth_files(self, reg):
        """Create or renew passphrase and SSL files for suite 'reg'."""
        # Suite service directory.
        srv_d = self.get_suite_srv_dir(reg)
        os.makedirs(srv_d, exist_ok=True)

        # Create a new passphrase for the suite if necessary.
        if not self._locate_item(self.FILE_BASE_PASSPHRASE, srv_d):
            import random
            self._dump_item(srv_d, self.FILE_BASE_PASSPHRASE, ''.join(
                random.sample(self.PASSPHRASE_CHARSET, self.PASSPHRASE_LEN)))

    @staticmethod
    def _dump_item(path, item, value):
        """Dump "value" to a file called "item" in the directory "path".

        1. File permission should already be user-read-write-only on
           creation by mkstemp.
        2. The combination of os.fsync and os.rename should guarantee
           that we don't end up with an incomplete file.
        """
        os.makedirs(path, exist_ok=True)
        from tempfile import NamedTemporaryFile
        handle = NamedTemporaryFile(prefix=item, dir=path, delete=False)
        try:
            handle.write(value.encode())
        except AttributeError:
            handle.write(value)
        os.fsync(handle.fileno())
        handle.close()
        fname = os.path.join(path, item)
        os.rename(handle.name, fname)
        LOG.debug('Generated %s', fname)

    def _get_cache_dir(self, reg, owner, host):
        """Return the cache directory for remote suite service files."""
        return os.path.join(
            os.path.expanduser("~"), ".cylc", self.DIR_BASE_AUTH,
            "%s@%s" % (owner, host), reg)

    def get_suite_title(self, reg):
        """Return the the suite title without a full file parse

        Limitations:
        * 1st line of title only.
        * Assume title is not in an include-file.
        """
        title = self.NO_TITLE
        for line in open(self.get_suite_rc(reg), 'rb'):
            line = line.decode()
            if line.lstrip().startswith("[meta]"):
                # continue : title comes inside [meta] section
                continue
            elif line.lstrip().startswith("["):
                # abort: title comes before first [section]
                break
            match = self.REC_TITLE.match(line)
            if match:
                title = match.groups()[0].strip('"\'')
        return title

    def _is_local_auth_ok(self, reg, owner, host):
        """Return True if it is OK to use local passphrase file.

        Use values in ~/cylc-run/REG/.service/contact to make a judgement.
        Cache results in self.can_use_load_auths.
        """
        if (reg, owner, host) not in self.can_use_load_auths:
            if is_remote(host, owner):
                fname = os.path.join(
                    self.get_suite_srv_dir(reg), self.FILE_BASE_CONTACT)
                data = {}
                try:
                    for line in open(fname):
                        key, value = (
                            [item.strip() for item in line.split("=", 1)])
                        data[key] = value
                except (IOError, ValueError):
                    # No contact file
                    self.can_use_load_auths[(reg, owner, host)] = False
                else:
                    # Contact file exists, check values match
                    if owner is None:
                        owner = get_user()
                    if host is None:
                        host = get_host()
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
        if not is_remote(host, owner):
            return
        if host is None:
            host = 'localhost'
        if owner is None:
            owner = get_user()
        if item == self.FILE_BASE_CONTACT and not is_remote_host(host):
            # Attempt to read suite contact file via the local filesystem.
            path = r'%(run_d)s/%(srv_base)s' % {
                'run_d': glbl_cfg().get_derived_host_item(
                    reg, 'suite run directory', 'localhost', owner,
                    replace_home=False),
                'srv_base': self.DIR_BASE_SRV,
            }
            content = self._load_local_item(item, path)
            if content is not None:
                return content
            # Else drop through and attempt via ssh to the suite account.
        # Prefix STDOUT to ensure returned content is relevant
        prefix = r'[CYLC-AUTH] %(suite)s' % {'suite': reg}
        # Attempt to cat passphrase file under suite service directory
        script = (
            r"""echo '%(prefix)s'; """
            r'''cat "%(run_d)s/%(srv_base)s/%(item)s"'''
        ) % {
            'prefix': prefix,
            'run_d': glbl_cfg().get_derived_host_item(
                reg, 'suite run directory', host, owner),
            'srv_base': self.DIR_BASE_SRV,
            'item': item
        }
        import shlex
        command = shlex.split(
            glbl_cfg().get_host_item('ssh command', host, owner))
        command += ['-n', owner + '@' + host, script]
        from subprocess import Popen, PIPE
        try:
            proc = Popen(
                command, stdin=open(os.devnull), stdout=PIPE, stderr=PIPE)
        except OSError:
            if cylc.flags.debug:
                import traceback
                traceback.print_exc()
            return
        out, err = (f.decode() for f in proc.communicate())
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
            LOG.debug(
                '$ %(command)s  # code=%(ret_code)s\n%(err)s',
                {
                    'command': command,
                    # STDOUT may contain passphrase, so not safe to print
                    # 'out': out,
                    'err': err,
                    'ret_code': ret_code,
                })
            return
        return content

    @staticmethod
    def _locate_item(item, path):
        """Locate a service item in "path"."""
        fname = os.path.join(path, item)
        if os.path.exists(fname):
            return fname
