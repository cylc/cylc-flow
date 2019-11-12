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
from functools import lru_cache
import os
import re
import shutil
import stat
from string import ascii_letters, digits
import zmq.auth

from cylc.flow import LOG
from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.exceptions import SuiteServiceFileError
from cylc.flow.pathutil import get_remote_suite_run_dir, get_suite_run_dir
import cylc.flow.flags
from cylc.flow.hostuserutil import (
    get_host, get_user, is_remote, is_remote_host, is_remote_user)
from cylc.flow.unicode_rules import SuiteNameValidator


class SuiteFiles:
    """Files and directories located in the suite directory."""

    SUITE_RC = 'suite.rc'
    """The suite configuration file."""

    class Service:
        """The directory containing Cylc system files."""

        DIRNAME = '.service'
        """The name of this directory."""

        CONTACT = 'contact'
        """Contains settings for the running suite.

        For details of the fields see ``ContactFileFields``.
        """

        CONTACT2 = 'contact2'
        """Same as ``CONTACT``, installed on remote platforms."""

        PASSPHRASE = 'passphrase'
        """The suite authentication token."""

        SOURCE = 'source'
        """Symlink to the suite definition (suite dir)."""


class ContactFileFields:
    """Field names present in ``SuiteFiles.Service.CONTACT``.

    These describe properties of a running suite.

    .. note::

       The presence of this file indicates that the suite is running as it is
       removed when a suite shuts-down, however, in exceptional circumstances,
       if a suite is not properly shut-down this file may be left behind.

    """

    API = 'CYLC_API'
    """The Suite API version string."""

    COMMS_PROTOCOL_2 = 'CYLC_COMMS_PROTOCOL_2'  # indirect comms

    HOST = 'CYLC_SUITE_HOST'
    """The name of the host the suite server process is running on."""

    NAME = 'CYLC_SUITE_NAME'
    """The name of the suite."""

    OWNER = 'CYLC_SUITE_OWNER'
    """The user account under which the suite server process is running."""

    PROCESS = 'CYLC_SUITE_PROCESS'
    """The process ID of the running suite on ``CYLC_SUITE_HOST``."""

    PORT = 'CYLC_SUITE_PORT'
    """The port Cylc uses to communicate with this suite."""

    SSH_USE_LOGIN_SHELL = 'CYLC_SSH_USE_LOGIN_SHELL'
    """TODO: Unused at present, waiting on #2975 (#3327)."""

    SUITE_RUN_DIR_ON_SUITE_HOST = 'CYLC_SUITE_RUN_DIR_ON_SUITE_HOST'
    """The path to the suite run directory as seen from ``HOST``."""

    TASK_MSG_MAX_TRIES = 'CYLC_TASK_MSG_MAX_TRIES'
    """TODO: Unused at present, waiting on #3331."""

    TASK_MSG_RETRY_INTVL = 'CYLC_TASK_MSG_RETRY_INTVL'
    """TODO: Unused at present, waiting on #3331."""

    TASK_MSG_TIMEOUT = 'CYLC_TASK_MSG_TIMEOUT'
    """TODO: Unused at present, waiting on #3331."""

    UUID = 'CYLC_SUITE_UUID'
    """Unique ID for this run of the suite."""

    VERSION = 'CYLC_VERSION'
    """The Cylc version under which the suite is running."""


class UserFiles:
    """Directory containing config and auth files for a user."""

    DIRNAME = '.cylc'
    """The name of this directory."""

    class Auth:
        """Cache for remote service files."""

        DIRNAME = 'auth'
        """The name of this directory."""

        PUBLIC_KEY_DIRNAME = 'public_key'
        """The name of the directory holding the public key certificate."""

        PRIVATE_KEY_DIRNAME = 'private_key'
        """The name of the directory holding the private key certificate."""

        SERVER_TAG = 'server'  # for server, i.e. suite, keys
        CLIENT_TAG = 'client'  # for client, i.e. user, keys
        PUBLIC_TAG = '.key'  # for public keys
        PRIVATE_TAG = '.key_secret'  # for private ('secret') keys
        """Keyword identifiers used to form the certificate names, as below.
           Note: the public/private tags are set (by default) by CurveZMQ.
        """

        SERVER_PUBLIC_KEY_CERTIFICATE = SERVER_TAG + PUBLIC_TAG
        CLIENT_PUBLIC_KEY_CERTIFICATE = CLIENT_TAG + PUBLIC_TAG
        SERVER_PRIVATE_KEY_CERTIFICATE = SERVER_TAG + PRIVATE_TAG
        CLIENT_PRIVATE_KEY_CERTIFICATE = CLIENT_TAG + PRIVATE_TAG
        """The name of the authentication certificates."""

    @classmethod
    def get_path(cls, include_auth_dirname=True):
        """Return the path to this directory for the current user."""
        path_components = [os.path.expanduser("~"), cls.DIRNAME]
        if include_auth_dirname:
            path_components.append(cls.Auth.DIRNAME)
        return os.path.join(*path_components)

    @classmethod
    def get_user_certificate_full_path(cls, private=False):
        """Return the directory path of a certificate for the current user."""
        if private:
            certificate_dirname = cls.Auth.PRIVATE_KEY_DIRNAME
        else:
            certificate_dirname = cls.Auth.PUBLIC_KEY_DIRNAME
        return os.path.join(
            cls.get_path(),
            certificate_dirname
        )


REG_DELIM = "/"

NO_TITLE = "No title provided"
REC_TITLE = re.compile(r"^\s*title\s*=\s*(.*)\s*$")

PASSPHRASE_CHARSET = ascii_letters + digits
PASSPHRASE_LEN = 20

PS_OPTS = '-opid,args'

CONTACT_FILE_EXISTS_MSG = r"""suite contact file exists: %(fname)s

Suite "%(suite)s" is already running, and listening at "%(host)s:%(port)s".

To start a new run, stop the old one first with one or more of these:
* cylc stop %(suite)s              # wait for active tasks/event handlers
* cylc stop --kill %(suite)s       # kill active tasks and wait

* cylc stop --now %(suite)s        # don't wait for active tasks
* cylc stop --now --now %(suite)s  # don't wait
* ssh -n "%(host)s" kill %(pid)s   # final brute force!
"""


def detect_old_contact_file(reg, check_host_port=None):
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
        data = load_contact_file(reg)
        old_host = data[ContactFileFields.HOST]
        old_port = data[ContactFileFields.PORT]
        old_proc_str = data[ContactFileFields.PROCESS]
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
    cmd = ["timeout", "10", "ps", PS_OPTS, str(old_pid_str)]
    if is_remote_host(old_host):
        import shlex
        ssh_str = str(glbl_cfg().get_host_item("ssh command", old_host))
        cmd = shlex.split(ssh_str) + ["-n", old_host] + cmd
    from subprocess import Popen, PIPE, DEVNULL  # nosec
    from time import sleep, time
    proc = Popen(cmd, stdin=DEVNULL, stdout=PIPE, stderr=PIPE)  # nosec
    # Terminate command after 10 seconds to prevent hanging SSH, etc.
    timeout = time() + 10.0
    while proc.poll() is None:
        if time() > timeout:
            proc.terminate()
        sleep(0.1)
    fname = get_contact_file(reg)
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
        CONTACT_FILE_EXISTS_MSG % {
            "host": old_host,
            "port": old_port,
            "pid": old_pid_str,
            "fname": fname,
            "suite": reg,
        }
    )


def dump_contact_file(reg, data):
    """Create contact file. Data should be a key=value dict."""
    # Note:
    # 1st fsync for writing the content of the contact file to disk.
    # 2nd fsync for writing the file metadata of the contact file to disk.
    # The double fsync logic ensures that if the contact file is written to
    # a shared file system e.g. via NFS, it will be immediately visible
    # from by a process on other hosts after the current process returns.
    with open(get_contact_file(reg), "wb") as handle:
        for key, value in sorted(data.items()):
            handle.write(("%s=%s\n" % (key, value)).encode())
        os.fsync(handle.fileno())
    dir_fileno = os.open(get_suite_srv_dir(reg), os.O_DIRECTORY)
    os.fsync(dir_fileno)
    os.close(dir_fileno)


def get_contact_file(reg):
    """Return name of contact file."""
    return os.path.join(
        get_suite_srv_dir(reg), SuiteFiles.Service.CONTACT)


def get_auth_item(item, reg, owner=None, host=None, content=False):
    """Locate/load passphrase, SSL private key, SSL certificate, etc.

    Return file name, or content of file if content=True is set.
    Files are searched from these locations in order:

    1/ For running task jobs, service directory under:
       a/ $CYLC_SUITE_RUN_DIR for remote jobs.
       b/ $CYLC_SUITE_RUN_DIR_ON_SUITE_HOST for local jobs or remote jobs
          with SSH messaging.

    2/ For suite on local user@host. The suite service directory.

    3/ Location under $HOME/.cylc/ for remote suite control from accounts
       that do not actually need the suite definition directory to be
       installed:
       $HOME/.cylc/auth/SUITE_OWNER@SUITE_HOST/SUITE_NAME/

    4/ For remote suites, try locating the file from the suite service
       directory on remote owner@host via SSH. If content=False, the value
       of the located file will be dumped under:
       $HOME/.cylc/auth/SUITE_OWNER@SUITE_HOST/SUITE_NAME/

    """
    if item not in [
            SuiteFiles.Service.PASSPHRASE, SuiteFiles.Service.CONTACT,
            SuiteFiles.Service.CONTACT2,
            UserFiles.Auth.SERVER_PRIVATE_KEY_CERTIFICATE,
            UserFiles.Auth.SERVER_PUBLIC_KEY_CERTIFICATE]:
        raise ValueError("%s: item not recognised" % item)

    # For a UserFiles.Auth.SERVER_..._KEY_CERTIFICATE, only need to check Case
    # '3/' (always ignore content i.e. content=False), so check these first:
    if item in (UserFiles.Auth.SERVER_PRIVATE_KEY_CERTIFICATE,
                UserFiles.Auth.SERVER_PUBLIC_KEY_CERTIFICATE):
        auth_path = os.path.join(
            get_suite_srv_dir(reg), UserFiles.Auth.DIRNAME)
        public_key_dir, private_key_dir = return_key_locations(auth_path)
        if item == UserFiles.Auth.SERVER_PRIVATE_KEY_CERTIFICATE:
            path = private_key_dir
        else:
            path = public_key_dir
        value = _locate_item(item, path)
        if value:
            return value

    if reg == os.getenv('CYLC_SUITE_NAME'):
        env_keys = []
        if 'CYLC_SUITE_RUN_DIR' in os.environ:
            # 1(a)/ Task messaging call.
            env_keys.append('CYLC_SUITE_RUN_DIR')
        elif ContactFileFields.SUITE_RUN_DIR_ON_SUITE_HOST in os.environ:
            # 1(b)/ Task messaging call via ssh messaging.
            env_keys.append(ContactFileFields.SUITE_RUN_DIR_ON_SUITE_HOST)
        for key in env_keys:
            path = os.path.join(os.environ[key], SuiteFiles.Service.DIRNAME)
            if content:
                value = _load_local_item(item, path)
            else:
                value = _locate_item(item, path)
            if value:
                return value
    # 2/ Local suite service directory
    if _is_local_auth_ok(reg, owner, host):
        path = get_suite_srv_dir(reg)
        if content:
            value = _load_local_item(item, path)
        else:
            value = _locate_item(item, path)
        if value:
            return value
    # 3/ Disk cache for remote suites
    if owner is not None and host is not None:
        paths = [_get_cache_dir(reg, owner, host)]
        short_host = host.split('.', 1)[0]
        if short_host != host:
            paths.append(_get_cache_dir(reg, owner, short_host))
        for path in paths:
            if content:
                value = _load_local_item(item, path)
            else:
                value = _locate_item(item, path)
            if value:
                return value

    # 4/ Use SSH to load content from remote owner@host
    # Note: It is not possible to find ".service/contact2" on the suite
    # host, because it is installed on task host by "cylc remote-init" on
    # demand.
    if item != SuiteFiles.Service.CONTACT2:
        value = _load_remote_item(item, reg, owner, host)
        if value:
            if not content:
                path = _get_cache_dir(reg, owner, host)
                _dump_item(path, item, value)
                value = os.path.join(path, item)
            return value

    raise SuiteServiceFileError("Couldn't get %s" % item)


def get_suite_rc(reg, suite_owner=None):
    """Return the suite.rc path of a suite."""
    return os.path.join(
        get_suite_source_dir(reg, suite_owner),
        SuiteFiles.SUITE_RC)


def get_suite_source_dir(reg, suite_owner=None):
    """Return the source directory path of a suite.

    Will register un-registered suites located in the cylc run dir.
    """
    srv_d = get_suite_srv_dir(reg, suite_owner)
    fname = os.path.join(srv_d, SuiteFiles.Service.SOURCE)
    try:
        source = os.readlink(fname)
    except OSError:
        suite_d = os.path.dirname(srv_d)
        if os.path.exists(suite_d) and not is_remote_user(suite_owner):
            # suite exists but is not yet registered
            register(reg=reg, source=suite_d)
            return suite_d
        else:
            raise SuiteServiceFileError("Suite not found %s" % reg)
    else:
        if os.path.isabs(source):
            return source
        else:
            return os.path.normpath(os.path.join(srv_d, source))


def get_suite_srv_dir(reg, suite_owner=None):
    """Return service directory of a suite."""
    if not suite_owner:
        suite_owner = get_user()
    run_d = os.getenv("CYLC_SUITE_RUN_DIR")
    if (not run_d or os.getenv("CYLC_SUITE_NAME") != reg or
            os.getenv("CYLC_SUITE_OWNER") != suite_owner):
        run_d = get_suite_run_dir(reg)
    return os.path.join(run_d, SuiteFiles.Service.DIRNAME)


def load_contact_file(reg, owner=None, host=None, file_base=None):
    """Load contact file. Return data as key=value dict."""
    if not file_base:
        file_base = SuiteFiles.Service.CONTACT
    file_content = get_auth_item(
        file_base, reg, owner, host, content=True)
    data = {}
    for line in file_content.splitlines():
        key, value = [item.strip() for item in line.split("=", 1)]
        data[key] = value
    return data


def parse_suite_arg(options, arg):
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
        path = get_suite_rc(arg, options.suite_owner)
        name = arg
    except SuiteServiceFileError:
        arg = os.path.abspath(arg)
        if os.path.isdir(arg):
            path = os.path.join(arg, SuiteFiles.SUITE_RC)
            name = os.path.basename(arg)
        else:
            path = arg
            name = os.path.basename(os.path.dirname(arg))
    return name, path


def register(reg=None, source=None, redirect=False, rundir=None):
    """Register a suite, or renew its registration.

    Create suite service directory and symlink to suite source location.

    Args:
        reg (str): suite name, default basename($PWD).
        source (str): directory location of suite.rc file, default $PWD.
        redirect (bool): allow reuse of existing name and run directory.
        rundir (str): for overriding the default cylc-run directory.

    Return:
        str: The registered suite name (which may be computed here).

    Raise:
        SuiteServiceFileError:
            No suite.rc file found in source location.
            Illegal name (can look like a relative path, but not absolute).
            Another suite already has this name (unless --redirect).
    """
    if reg is None:
        reg = os.path.basename(os.getcwd())

    is_valid, message = SuiteNameValidator.validate(reg)
    if not is_valid:
        raise SuiteServiceFileError(
            f'invalid suite name - {message}'
        )

    if os.path.isabs(reg):
        raise SuiteServiceFileError(
            "suite name cannot be an absolute path: %s" % reg)

    if source is not None:
        if os.path.basename(source) == SuiteFiles.SUITE_RC:
            source = os.path.dirname(source)
    else:
        source = os.getcwd()

    # suite.rc must exist so we can detect accidentally reversed args.
    source = os.path.abspath(source)
    if not os.path.isfile(os.path.join(source, SuiteFiles.SUITE_RC)):
        raise SuiteServiceFileError("no suite.rc in %s" % source)

    # Create service dir if necessary.
    srv_d = get_suite_srv_dir(reg)
    if rundir is None:
        os.makedirs(srv_d, exist_ok=True)
    else:
        suite_run_d, srv_d_name = os.path.split(srv_d)
        alt_suite_run_d = os.path.join(rundir, reg)
        alt_srv_d = os.path.join(rundir, reg, srv_d_name)
        os.makedirs(alt_srv_d, exist_ok=True)
        os.makedirs(os.path.dirname(suite_run_d), exist_ok=True)
        if os.path.islink(suite_run_d) and not os.path.exists(suite_run_d):
            # Remove a bad symlink.
            os.unlink(suite_run_d)
        if not os.path.exists(suite_run_d):
            os.symlink(alt_suite_run_d, suite_run_d)
        elif not os.path.islink(suite_run_d):
            raise SuiteServiceFileError(
                f"Run directory '{suite_run_d}' already exists.")
        elif alt_suite_run_d != os.readlink(suite_run_d):
            target = os.readlink(suite_run_d)
            raise SuiteServiceFileError(
                f"Symlink '{suite_run_d}' already points to {target}.")
        # (else already the right symlink)

    # See if suite already has a source or not
    try:
        orig_source = os.readlink(
            os.path.join(srv_d, SuiteFiles.Service.SOURCE))
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
        os.unlink(os.path.join(srv_d, SuiteFiles.Service.SOURCE))

    # Create symlink to the suite, if it doesn't already exist.
    if orig_source is None or source != orig_source:
        target = os.path.join(srv_d, SuiteFiles.Service.SOURCE)
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


def create_auth_files(reg):
    """Create or renew passphrase and SSL files for suite 'reg'."""
    # Suite service directory.
    srv_d = get_suite_srv_dir(reg)
    os.makedirs(srv_d, exist_ok=True)

    # If necessary, generate directory holding (in separate sub-dirs) the
    # server (suite) public and private keys for authentication:
    ensure_suite_keys_exist(srv_d)

    # Create a new passphrase for the suite if necessary.
    if not _locate_item(SuiteFiles.Service.PASSPHRASE, srv_d):
        import random
        _dump_item(srv_d, SuiteFiles.Service.PASSPHRASE, ''.join(
            random.sample(PASSPHRASE_CHARSET, PASSPHRASE_LEN)))


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


def _get_cache_dir(reg, owner, host):
    """Return the cache directory for remote suite service files."""
    return os.path.join(
        UserFiles.get_path(),
        "%s@%s" % (owner, host), reg
    )


def get_suite_title(reg):
    """Return the the suite title without a full file parse

    Limitations:
    * 1st line of title only.
    * Assume title is not in an include-file.
    """
    title = NO_TITLE
    for line in open(get_suite_rc(reg), 'rb'):
        line = line.decode()
        if line.lstrip().startswith("[meta]"):
            # continue : title comes inside [meta] section
            continue
        elif line.lstrip().startswith("["):
            # abort: title comes before first [section]
            break
        match = REC_TITLE.match(line)
        if match:
            title = match.groups()[0].strip('"\'')
    return title


@lru_cache()
def _is_local_auth_ok(reg, owner, host):
    """Return True if it is OK to use local passphrase file.

    Use values in ~/cylc-run/REG/.service/contact to make a judgement.
    """
    if is_remote(host, owner):
        fname = os.path.join(
            get_suite_srv_dir(reg), SuiteFiles.Service.CONTACT)
        data = {}
        try:
            for line in open(fname):
                key, value = (
                    [item.strip() for item in line.split("=", 1)])
                data[key] = value
        except (IOError, ValueError):
            # No contact file
            return False
        else:
            # Contact file exists, check values match
            if owner is None:
                owner = get_user()
            if host is None:
                host = get_host()
            host_value = data.get(ContactFileFields.HOST, "")
            return (
                reg == data.get(ContactFileFields.NAME) and
                owner == data.get(ContactFileFields.OWNER) and
                (
                    host == host_value or
                    host == host_value.split(".", 1)[0]  # no domain
                )
            )
    else:
        return True


def _load_local_item(item, path):
    """Load and return content of a file (item) in path."""
    try:
        with open(os.path.join(path, item)) as file_:
            return file_.read()
    except IOError:
        return None


def _load_remote_item(item, reg, owner, host):
    """Load content of service item from remote [owner@]host via SSH."""
    if not is_remote(host, owner):
        return
    if host is None:
        host = 'localhost'
    if owner is None:
        owner = get_user()
    if item == SuiteFiles.Service.CONTACT and not is_remote_host(host):
        # Attempt to read suite contact file via the local filesystem.
        path = r'%(run_d)s/%(srv_base)s' % {
            'run_d': get_remote_suite_run_dir('localhost', owner, reg),
            'srv_base': SuiteFiles.Service.DIRNAME,
        }
        content = _load_local_item(item, path)
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
        'run_d': get_remote_suite_run_dir(host, owner, reg),
        'srv_base': SuiteFiles.Service.DIRNAME,
        'item': item
    }
    import shlex
    command = shlex.split(
        glbl_cfg().get_host_item('ssh command', host, owner))
    command += ['-n', owner + '@' + host, script]
    from subprocess import Popen, PIPE, DEVNULL  # nosec
    try:
        proc = Popen(
            command, stdin=DEVNULL, stdout=PIPE, stderr=PIPE)  # nosec
    except OSError:
        if cylc.flow.flags.debug:
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


def _locate_item(item, path):
    """Locate a service item in "path"."""
    fname = os.path.join(path, item)
    if os.path.exists(fname):
        return fname


def return_key_locations(store_dir):
    """Return the paths to a directory's key files: (public, private)."""
    return (
        os.path.join(store_dir, UserFiles.Auth.PUBLIC_KEY_DIRNAME),
        os.path.join(store_dir, UserFiles.Auth.PRIVATE_KEY_DIRNAME)
    )


def lockdown_private_keys(key_file_path):
    """Change key file permissions to lock from other users."""
    # This means that the owner can read & write, but all others cannot do
    # anything, to the file, i.e. 600 ('-rw-------.') Linux file permission.
    if not os.path.exists(key_file_path):
        raise FileNotFoundError(
            "Private key not found at location '%s'." % key_file_path)
    os.chmod(key_file_path, stat.S_IRUSR | stat.S_IWUSR)


def generate_key_store(store_parent_dir, keys_tag):
    """Generate two sub-directories, each having a file with a CURVE key.

    WARNING: be careful testing this. It uses 'shutil.rmtree' which will
    wipe the whole 'store_dir/UserFiles.Auth.DIRNAME' directory if it exists.

    Note: store_parent_dir must already exist as a valid directory.
    """

    # Define the directory structure to store the CURVE keys in
    store_dir = os.path.join(store_parent_dir, UserFiles.Auth.DIRNAME)
    public_key_loc, private_key_loc = return_key_locations(store_dir)

    # Create, or wipe, that directory structure
    for directory in [store_dir, public_key_loc, private_key_loc]:
        if os.path.exists(directory):
            shutil.rmtree(directory)  # WARNING: destructive, so take care
        os.mkdir(directory)

    # Make a new public-private CURVE key pair
    zmq.auth.create_certificates(store_dir, keys_tag)

    # Move key pair to appropriate directories & lock private key file
    for key_file in os.listdir(store_dir):
        if key_file.endswith(UserFiles.Auth.PUBLIC_TAG):
            shutil.move(os.path.join(store_dir, key_file),
                        os.path.join(public_key_loc, '.'))
            # The public key keeps standard 644 ('-rw-r--r--') file permission
        elif key_file.endswith(UserFiles.Auth.PRIVATE_TAG):
            loc = shutil.move(os.path.join(store_dir, key_file),
                              os.path.join(private_key_loc, '.'))
            # Now lock the prviate key in its permanent location
            try:
                lockdown_private_keys(loc)  # Linux File Permission now 600
            # Catch any and all errors here, since private keys must be
            # locked for the security (asymmetric cryptography) to work.
            except Exception:
                raise OSError("Unable to lock permissions of private " +
                              "keys for authentication. Abort.")


def ensure_dir_exists(dir_path):
    """Check for a directory at a path and create it if it does not exist."""
    if not os.path.exists(dir_path):
        os.mkdir(dir_path)


def ensure_keypair_exists(auth_parent_dir, auth_child_dir, tag):
    """Check if a set of public/private keys exist and if not, create them."""
    public_key_location, private_key_location = return_key_locations(
        auth_child_dir)  # where the keys should be, else where to create them
    if (os.path.exists(public_key_location) and
            os.path.exists(private_key_location)):
        return True
    else:
        # Ensure parent dir exists (child dir will be created if it does not)
        ensure_dir_exists(auth_parent_dir)
        try:
            generate_key_store(auth_parent_dir, tag)
            return True
        # Catch anything so we can otherwise be sure the key store exists.
        except Exception:
            LOG.exception("Failed to create %s authentication keys." % tag)
            return False


def ensure_user_keys_exist():
    """Make sure the user (client) public/private keys exist."""
    return ensure_keypair_exists(
        UserFiles.get_path(include_auth_dirname=False),
        UserFiles.get_path(),
        UserFiles.Auth.CLIENT_TAG
    )


def ensure_suite_keys_exist(suite_service_directory):
    """Make sure the suite (server) public/private keys exist."""
    return ensure_keypair_exists(
        suite_service_directory,
        os.path.join(suite_service_directory, UserFiles.Auth.DIRNAME),
        UserFiles.Auth.SERVER_TAG
    )
