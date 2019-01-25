#!/usr/bin/env python2

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
"""HTTP(S) client for suite runtime API.

Implementation currently via requests (urllib3) or urllib2.
"""

import os
import sys
from time import sleep
import traceback
from uuid import uuid4
import warnings


from cylc.cfgspec.glbl_cfg import glbl_cfg
from cylc.exceptions import CylcError
import cylc.flags
from cylc.network import NO_PASSPHRASE
from cylc.hostuserutil import get_host, get_fqdn_by_host, get_user
from cylc.suite_srv_files_mgr import (
    SuiteSrvFilesManager, SuiteServiceFileError)
from cylc.unicode_util import utf8_enforce
from cylc.version import CYLC_VERSION
from cylc.wallclock import get_current_time_string


# Note: This was renamed from ConnectionError to ClientError. ConnectionError
# is a built-in exception in Python 3.
class ClientError(Exception):

    """An error raised when the client has a general failure."""

    MESSAGE = "Client error: %s: %s"

    def __str__(self):
        return self.MESSAGE % (self.args[0], self.args[1])


class ClientConnectError(ClientError):

    """An error raised when the client cannot connect."""

    MESSAGE = "Cannot connect: %s: %s"
    STOPPED = "suite \"%s\" already stopped"

    def __str__(self):
        return self.MESSAGE % (self.args[0], self.args[1])


class ClientConnectedError(ClientError):

    """An error raised when the client gets a bad return code from server."""

    MESSAGE = "Bad return code: %s: %s"

    def __str__(self):
        return self.MESSAGE % (self.args[0], self.args[1])


class ClientDeniedError(ClientConnectedError):

    """An error raised when the client is not permitted to connect."""

    MESSAGE = "Not authorized: %s: %s: access type '%s'"

    def __str__(self):
        return self.MESSAGE % (self.args[0], self.args[1], self.args[2])


class ClientInfoError(ClientError):

    """An error raised when the client is unable to load the contact info."""

    MESSAGE = "Contact info not found for suite \"%s\", suite not running?"

    def __str__(self):
        return self.MESSAGE % (self.args[0])


class ClientInfoUUIDError(ClientInfoError):

    """An error on UUID mismatch between environment and contact info."""

    MESSAGE = "Suite UUID mismatch: environment=%s, contact-info=%s"

    def __str__(self):
        return self.MESSAGE % self.args


class ClientTimeout(ClientError):

    """An error raised on connection timeout."""

    MESSAGE = "Connection timeout: %s: %s"

    def __str__(self):
        return self.MESSAGE % (self.args[0], self.args[1])


class SuiteRuntimeServiceClient(object):
    """Client for calling the HTTP(S) API of running suites."""

    ANON_AUTH = ('anon', NO_PASSPHRASE, False)
    COMPAT_MAP = {  # Limited pre-7.5.0 API compat mapping
        'clear_broadcast': {0: 'broadcast/clear'},
        'expire_broadcast': {0: 'broadcast/expire'},
        'get_broadcast': {0: 'broadcast/get'},
        'get_info': {0: 'info/'},
        'get_suite_state_summary': {0: 'state/get_state_summary'},
        'put_broadcast': {0: 'broadcast/put'},
        'put_command': {0: 'command/'},
        'put_ext_trigger': {0: 'ext-trigger/put'},
        'put_messages': {0: 'message/put', 1: 'put_message'},
    }
    ERROR_NO_HTTPS_SUPPORT = (
        "ERROR: server has no HTTPS support," +
        " configure your global.rc file to use HTTP : {0}\n"
    )
    METHOD = 'POST'
    METHOD_POST = 'POST'
    METHOD_GET = 'GET'

    MSG_RETRY_INTVL = 5.0
    MSG_MAX_TRIES = 7
    MSG_TIMEOUT = 30.0

    def __init__(
            self, suite, owner=None, host=None, port=None, timeout=None,
            my_uuid=None, print_uuid=False, auth=None):
        self.suite = suite
        if not owner:
            owner = get_user()
        self.owner = owner
        self.host = host
        if self.host and self.host.split('.')[0] == 'localhost':
            self.host = get_host()
        elif self.host and '.' not in self.host:  # Not IP and no domain
            self.host = get_fqdn_by_host(self.host)
        self.port = port
        self.srv_files_mgr = SuiteSrvFilesManager()
        if timeout is not None:
            timeout = float(timeout)
        self.timeout = timeout
        self.my_uuid = my_uuid or uuid4()
        if print_uuid:
            sys.stderr.write('%s\n' % self.my_uuid)

        self.prog_name = os.path.basename(sys.argv[0])
        self.auth = auth
        self.session = None
        self.comms1 = {}  # content in primary contact file
        self.comms2 = {}  # content in extra contact file, e.g. contact via ssh

    def _compat(self, name, default=None):
        """Return server function name.

        Handle back-compat for pre-7.5.0 if relevant.
        """
        # Need to load contact info here to get API version.
        self._load_contact_info()
        if default is None:
            default = name
        return self.COMPAT_MAP[name].get(
            self.comms1.get(self.srv_files_mgr.KEY_API), default)

    def clear_broadcast(self, payload):
        """Clear broadcast runtime task settings."""
        return self._call_server(
            self._compat('clear_broadcast'), payload=payload)

    def expire_broadcast(self, **kwargs):
        """Expire broadcast runtime task settings."""
        return self._call_server(self._compat('expire_broadcast'), **kwargs)

    def get_broadcast(self, **kwargs):
        """Return broadcast settings."""
        return self._call_server(
            self._compat('get_broadcast'), method=self.METHOD_GET, **kwargs)

    def get_info(self, command, **kwargs):
        """Return suite info."""
        return self._call_server(
            self._compat('get_info', default='') + command,
            method=self.METHOD_GET, **kwargs)

    def get_latest_state(self, full_mode=False):
        """Return latest state of the suite (for the GUI)."""
        self._load_contact_info()
        if self.comms1.get(self.srv_files_mgr.KEY_API) == 0:
            # Basic compat for pre-7.5.0 suites
            # Full mode only.
            # Error content/size not supported.
            # Report made-up main loop interval of 5.0 seconds.
            return {
                'cylc_version': self.get_info('get_cylc_version'),
                'full_mode': full_mode,
                'summary': self.get_suite_state_summary(),
                'ancestors': self.get_info('get_first_parent_ancestors'),
                'ancestors_pruned': self.get_info(
                    'get_first_parent_ancestors', pruned=True),
                'descendants': self.get_info('get_first_parent_descendants'),
                'err_content': '',
                'err_size': 0,
                'mean_main_loop_interval': 5.0}
        else:
            return self._call_server(
                'get_latest_state',
                method=self.METHOD_GET, full_mode=full_mode)

    def get_suite_state_summary(self):
        """Return the global, task, and family summary data structures."""
        return utf8_enforce(self._call_server(
            self._compat('get_suite_state_summary'), method=self.METHOD_GET))

    def identify(self):
        """Return suite identity."""
        # Note on compat: Suites on 7.6.0 or above can just call "identify",
        # but has compat for "id/identity".
        return self._call_server('id/identify', method=self.METHOD_GET)

    def put_broadcast(self, payload):
        """Put/set broadcast runtime task settings."""
        return self._call_server(
            self._compat('put_broadcast'), payload=payload)

    def put_command(self, command, **kwargs):
        """Invoke suite command."""
        return self._call_server(
            self._compat('put_command', default='') + command, **kwargs)

    def put_ext_trigger(self, event_message, event_id):
        """Put external trigger."""
        return self._call_server(
            self._compat('put_ext_trigger'),
            event_message=event_message, event_id=event_id)

    def put_messages(self, payload):
        """Send task messages to suite server program.

        Arguments:
            payload (dict):
                task_job (str): Task job as "CYCLE/TASK_NAME/SUBMIT_NUM".
                event_time (str): Event time as string.
                messages (list): List in the form [[severity, message], ...].
        """
        retry_intvl = float(self.comms1.get(
            self.srv_files_mgr.KEY_TASK_MSG_RETRY_INTVL,
            self.MSG_RETRY_INTVL))
        max_tries = int(self.comms1.get(
            self.srv_files_mgr.KEY_TASK_MSG_MAX_TRIES,
            self.MSG_MAX_TRIES))
        for i in range(1, max_tries + 1):  # 1..max_tries inclusive
            orig_timeout = self.timeout
            if self.timeout is None:
                self.timeout = self.MSG_TIMEOUT
            try:
                func_name = self._compat('put_messages')
                if func_name == 'put_messages':
                    results = self._call_server(func_name, payload=payload)
                elif func_name == 'put_message':  # API 1, 7.5.0 compat
                    cycle, name = payload['task_job'].split('/')[0:2]
                    for severity, message in payload['messages']:
                        results.append(self._call_server(
                            func_name, task_id='%s.%s' % (name, cycle),
                            severity=severity, message=message))
                else:  # API 0, pre-7.5.0 compat, priority instead of severity
                    cycle, name = payload['task_job'].split('/')[0:2]
                    for severity, message in payload['messages']:
                        results.append(self._call_server(
                            func_name, task_id='%s.%s' % (name, cycle),
                            priority=severity, message=message))
            except ClientInfoError:
                # Contact info file not found, suite probably not running.
                # Don't bother with retry, suite restart will poll any way.
                raise
            except ClientError as exc:
                now = get_current_time_string()
                sys.stderr.write(
                    "%s WARNING - Message send failed, try %s of %s: %s\n" % (
                        now, i, max_tries, exc))
                if i < max_tries:
                    sys.stderr.write(
                        "   retry in %s seconds, timeout is %s\n" % (
                            retry_intvl, self.timeout))
                    sleep(retry_intvl)
                    # Reset in case contact info or passphrase change
                    self.comms1 = {}
                    self.host = None
                    self.port = None
                    self.auth = None
            else:
                if i > 1:
                    # Continue to write to STDERR, so users can easily see that
                    # it has recovered from previous failures.
                    sys.stderr.write(
                        "%s INFO - Send message: try %s of %s succeeded\n" % (
                            get_current_time_string(), i, max_tries))
                return results
            finally:
                self.timeout = orig_timeout

    def reset(self):
        """Compat method, does nothing."""
        pass

    def signout(self):
        """Tell server to forget this client."""
        return self._call_server('signout')

    def _call_server(self, function, method=METHOD, payload=None, **kwargs):
        """Build server URL + call it"""
        if self.comms2:
            return self._call_server_via_comms2(function, payload, **kwargs)
        url = self._call_server_get_url(function, **kwargs)
        # Remove proxy settings from environment for now
        environ = {}
        for key in ("http_proxy", "https_proxy"):
            val = os.environ.pop(key, None)
            if val:
                environ[key] = val
        try:
            return self.call_server_impl(url, method, payload)
        finally:
            os.environ.update(environ)

    def _call_server_get_url(self, function, **kwargs):
        """Build request URL."""
        scheme = self.comms1.get(self.srv_files_mgr.KEY_COMMS_PROTOCOL)
        if scheme is None:
            # Use standard setting from global configuration
            scheme = glbl_cfg().get(['communication', 'method'])
        url = '%s://%s:%s/%s' % (
            scheme, self.host, self.port, function)
        # If there are any parameters left in the dict after popping,
        # append them to the url.
        if kwargs:
            import urllib.parse
            params = urllib.parse.urlencode(kwargs, doseq=True)
            url += "?" + params
        return url

    def call_server_impl(self, url, method, payload):
        """Determine whether to use requests or urllib2 to call suite API."""
        impl = self._call_server_impl_urllib2
        try:
            import requests
        except ImportError:
            pass
        else:
            if [int(_) for _ in requests.__version__.split(".")] >= [2, 4, 2]:
                impl = self._call_server_impl_requests
        try:
            return impl(url, method, payload)
        except ClientConnectError as exc:
            if self.suite is None:
                raise
            # Cannot connect, perhaps suite is no longer running and is leaving
            # behind a contact file?
            try:
                self.srv_files_mgr.detect_old_contact_file(
                    self.suite, (self.host, self.port))
            except (AssertionError, SuiteServiceFileError):
                raise exc
            else:
                # self.srv_files_mgr.detect_old_contact_file should delete left
                # behind contact file if the old suite process no longer
                # exists. Should be safe to report that the suite has stopped.
                raise ClientConnectError(exc.args[0], exc.STOPPED % self.suite)

    def _call_server_impl_requests(self, url, method, payload):
        """Call server with "requests" library."""
        import requests
        # Filter InsecureRequestWarning from urlib3. We use verify=False
        # deliberately (and safely) for anonymous access.
        from requests.packages.urllib3.exceptions import InsecureRequestWarning
        warnings.simplefilter("ignore", InsecureRequestWarning)
        # Filter security warnings from urllib3 on python <2.7.9. Obviously, we
        # want to upgrade, but some sites have to run cylc on platforms with
        # python <2.7.9. On those platforms, these warnings serve no purpose
        # except to annoy or confuse users.
        if sys.version_info < (2, 7, 9):
            try:
                from requests.packages.urllib3.exceptions import (
                    InsecurePlatformWarning)
            except ImportError:
                pass
            else:
                warnings.simplefilter("ignore", InsecurePlatformWarning)
            try:
                from requests.packages.urllib3.exceptions import (
                    SNIMissingWarning)
            except ImportError:
                pass
            else:
                warnings.simplefilter("ignore", SNIMissingWarning)
        if self.session is None:
            self.session = requests.Session()

        if method == self.METHOD_POST:
            session_method = self.session.post
        else:
            session_method = self.session.get
        scheme = url.split(':', 1)[0]  # Can use urlparse?
        username, password, verify = self._get_auth(scheme)
        try:
            ret = session_method(
                url,
                json=payload,
                verify=verify,
                proxies={},
                headers=self._get_headers(),
                auth=requests.auth.HTTPDigestAuth(username, password),
                timeout=self.timeout
            )
        except requests.exceptions.SSLError as exc:
            if "unknown protocol" in str(exc) and url.startswith("https:"):
                # Server is using http rather than https, for some reason.
                sys.stderr.write(self.ERROR_NO_HTTPS_SUPPORT.format(exc))
                raise CylcError(
                    "Cannot issue commands over unsecured http.")
            if cylc.flags.debug:
                traceback.print_exc()
            raise ClientConnectError(url, exc)
        except requests.exceptions.Timeout as exc:
            if cylc.flags.debug:
                traceback.print_exc()
            raise ClientTimeout(url, exc)
        except requests.exceptions.RequestException as exc:
            if cylc.flags.debug:
                traceback.print_exc()
            raise ClientConnectError(url, exc)
        if ret.status_code == 401:
            access_desc = 'private'
            if self.auth == self.ANON_AUTH:
                access_desc = 'public'
            raise ClientDeniedError(url, self.prog_name, access_desc)
        if ret.status_code >= 400:
            exception_text = get_exception_from_html(ret.text)
            if exception_text:
                sys.stderr.write(exception_text)
            else:
                sys.stderr.write(ret.text)
        try:
            ret.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            if cylc.flags.debug:
                traceback.print_exc()
            raise ClientConnectedError(url, exc)
        if self.auth and self.auth[1] != NO_PASSPHRASE:
            self.srv_files_mgr.cache_passphrase(
                self.suite, self.owner, self.host, self.auth[1])
        try:
            return ret.json()
        except ValueError:
            return ret.text

    def _call_server_impl_urllib2(self, url, method, payload):
        """Call server with "urllib2" library."""
        import json
        import urllib.request, urllib.error
        import ssl
        unverified_context = getattr(ssl, '_create_unverified_context', None)
        if unverified_context is not None:
            ssl._create_default_https_context = unverified_context

        scheme = url.split(':', 1)[0]  # Can use urlparse?
        username, password = self._get_auth(scheme)[0:2]
        auth_manager = urllib.request.HTTPPasswordMgrWithDefaultRealm()
        auth_manager.add_password(None, url, username, password)
        auth = urllib.request.HTTPDigestAuthHandler(auth_manager)
        opener = urllib.request.build_opener(
            auth, urllib.request.HTTPSHandler())
        headers_list = list(self._get_headers().items())
        if payload:
            payload = json.dumps(payload)
            headers_list.append(('Accept', 'application/json'))
            json_headers = {'Content-Type': 'application/json',
                            'Content-Length': len(payload)}
        else:
            payload = None
            json_headers = {'Content-Length': 0}
        opener.addheaders = headers_list
        req = urllib.request.Request(url, payload, json_headers)

        # This is an unpleasant monkey patch, but there isn't an
        # alternative. urllib2 uses POST if there is a data payload
        # but that is not the correct criterion.
        # The difference is basically that POST changes
        # server state and GET doesn't.
        req.get_method = lambda: method
        try:
            response = opener.open(req, timeout=self.timeout)
        except urllib.error.URLError as exc:
            if "unknown protocol" in str(exc) and url.startswith("https:"):
                # Server is using http rather than https, for some reason.
                sys.stderr.write(self.ERROR_NO_HTTPS_SUPPORT.format(exc))
                raise CylcError(
                    "Cannot issue commands over unsecured http.")
            if cylc.flags.debug:
                traceback.print_exc()
            if "timed out" in str(exc):
                raise ClientTimeout(url, exc)
            else:
                raise ClientConnectError(url, exc)
        except Exception as exc:
            if cylc.flags.debug:
                traceback.print_exc()
            raise ClientError(url, exc)

        if response.getcode() == 401:
            access_desc = 'private'
            if self.auth == self.ANON_AUTH:
                access_desc = 'public'
            raise ClientDeniedError(url, self.prog_name, access_desc)
        response_text = response.read()
        if response.getcode() >= 400:
            exception_text = get_exception_from_html(response_text)
            if exception_text:
                sys.stderr.write(exception_text)
            else:
                sys.stderr.write(response_text)
            raise ClientConnectedError(
                url,
                "%s HTTP return code" % response.getcode())
        if self.auth and self.auth[1] != NO_PASSPHRASE:
            self.srv_files_mgr.cache_passphrase(
                self.suite, self.owner, self.host, self.auth[1])

        try:
            return json.loads(response_text)
        except ValueError:
            return response_text

    def _call_server_via_comms2(self, function, payload, **kwargs):
        """Call server via "cylc client --use-ssh".

        Call "cylc client --use-ssh" using `subprocess.Popen`. Payload and
        arguments of the API method are serialized as JSON and are written to a
        temporary file, which is then used as the STDIN of the "cylc client"
        command. The external call here should be even safer than a direct
        HTTP(S) call, as it can be blocked by SSH before it even gets a chance
        to make the subsequent HTTP(S) call.

        Arguments:
            function (str): name of API method, argument 1 of "cylc client".
            payload (str): extra data or information for the API method.
            **kwargs (dict): arguments for the API method.
        """
        import json
        from cylc.remote import remote_cylc_cmd
        command = ["client", function, self.suite]
        if payload:
            kwargs["payload"] = payload
        if kwargs:
            from tempfile import TemporaryFile
            stdin = TemporaryFile()
            json.dump(kwargs, stdin)
            stdin.seek(0)
        else:
            # With stdin=None, `remote_cylc_cmd` will:
            # * Set stdin to open(os.devnull)
            # * Add `-n` to the SSH command
            stdin = None
        proc = remote_cylc_cmd(
            command, self.owner, self.host, capture_process=True,
            ssh_login_shell=(self.comms1.get(
                self.srv_files_mgr.KEY_SSH_USE_LOGIN_SHELL
            ) in ['True', 'true']),
            ssh_cylc=(r'%s/bin/cylc' % self.comms1.get(
                self.srv_files_mgr.KEY_DIR_ON_SUITE_HOST)
            ),
            stdin=stdin,
        )
        out = proc.communicate()[0]
        return_code = proc.wait()
        if return_code:
            from pipes import quote
            command_str = " ".join(quote(item) for item in command)
            raise ClientError(command_str, "return-code=%d" % return_code)
        return json.loads(out)

    def _get_auth(self, protocol):
        """Return a user/password Digest Auth."""
        if self.auth is None:
            self.auth = self.ANON_AUTH
            try:
                pphrase = self.srv_files_mgr.get_auth_item(
                    self.srv_files_mgr.FILE_BASE_PASSPHRASE,
                    self.suite, self.owner, self.host, content=True)
                if protocol == 'https':
                    verify = self.srv_files_mgr.get_auth_item(
                        self.srv_files_mgr.FILE_BASE_SSL_CERT,
                        self.suite, self.owner, self.host)
                else:
                    verify = False
            except SuiteServiceFileError:
                pass
            else:
                if pphrase and pphrase != NO_PASSPHRASE:
                    self.auth = ('cylc', pphrase, verify)
        return self.auth

    def _get_headers(self):
        """Return HTTP headers identifying the client."""
        user_agent_string = (
            "cylc/%s prog_name/%s uuid/%s" % (
                CYLC_VERSION, self.prog_name, self.my_uuid
            )
        )
        auth_info = "%s@%s" % (get_user(), get_host())
        return {"User-Agent": user_agent_string,
                "From": auth_info}

    def _load_contact_info(self):
        """Obtain suite owner, host, port info.

        Determine host and port using content in port file, unless already
        specified.
        """
        if self.host and self.port:
            return
        if self.port:
            # In case the contact file is corrupted, user can specify the port.
            self.host = get_host()
            return
        try:
            # Always trust the values in the contact file otherwise.
            self.comms1 = self.srv_files_mgr.load_contact_file(
                self.suite, self.owner, self.host)
            # Port inside "try" block, as it needs a type conversion
            self.port = int(self.comms1.get(self.srv_files_mgr.KEY_PORT))
        except (IOError, ValueError, SuiteServiceFileError):
            raise ClientInfoError(self.suite)
        else:
            # Check mismatch suite UUID
            env_suite = os.getenv(self.srv_files_mgr.KEY_NAME)
            env_uuid = os.getenv(self.srv_files_mgr.KEY_UUID)
            if (self.suite and env_suite and env_suite == self.suite and
                    env_uuid and
                    env_uuid != self.comms1.get(self.srv_files_mgr.KEY_UUID)):
                raise ClientInfoUUIDError(
                    env_uuid, self.comms1[self.srv_files_mgr.KEY_UUID])
            # All good
            self.host = self.comms1.get(self.srv_files_mgr.KEY_HOST)
            self.owner = self.comms1.get(self.srv_files_mgr.KEY_OWNER)
            if self.srv_files_mgr.KEY_API not in self.comms1:
                self.comms1[self.srv_files_mgr.KEY_API] = 0  # <=7.5.0 compat
        # Indirect comms settings
        self.comms2.clear()
        try:
            self.comms2.update(self.srv_files_mgr.load_contact_file(
                self.suite, self.owner, self.host,
                SuiteSrvFilesManager.FILE_BASE_CONTACT2))
        except SuiteServiceFileError:
            pass


def get_exception_from_html(html_text):
    """Return any content inside a <pre> block with id 'traceback', or None.

    Return e.g. 'abcdef' for text like '<body><pre id="traceback">
    abcdef
    </pre></body>'.

    """
    from html.parser import HTMLParser, HTMLParseError

    class ExceptionPreReader(HTMLParser):
        """Read exception from <pre id="traceback">...</pre> element."""
        def __init__(self):
            HTMLParser.__init__(self)
            self.is_in_traceback_pre = False
            self.exception_text = None

        def handle_starttag(self, tag, attrs):
            """Set is_in_traceback_pre to True if in <pre id="traceback">."""
            self.is_in_traceback_pre = (
                tag == 'pre' and
                any(attr == ('id', 'traceback') for attr in attrs))

        def handle_endtag(self, tag):
            """Set is_in_traceback_pre to False."""
            self.is_in_traceback_pre = False

        def handle_data(self, data):
            """Get text data in traceback "pre"."""
            if self.is_in_traceback_pre:
                if self.exception_text is None:
                    self.exception_text = ''
                self.exception_text += data

    parser = ExceptionPreReader()
    try:
        parser.feed(parser.unescape(html_text))
        parser.close()
    except HTMLParseError:
        return None
    return parser.exception_text
