#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2018 NIWA
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
        'get_tasks_by_state': {0: 'state/get_tasks_by_state'},
        'put_broadcast': {0: 'broadcast/put'},
        'put_command': {0: 'command/'},
        'put_ext_trigger': {0: 'ext-trigger/put'},
        'put_message': {0: 'message/put'},
    }
    ERROR_NO_HTTPS_SUPPORT = (
        "ERROR: server has no HTTPS support," +
        " configure your global.rc file to use HTTP : {0}\n"
    )
    METHOD = 'POST'
    METHOD_POST = 'POST'
    METHOD_GET = 'GET'

    def __init__(
            self, suite, owner=None, host=None, port=None, timeout=None,
            my_uuid=None, print_uuid=False, comms_protocol=None, auth=None):
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
        self.comms_protocol = comms_protocol
        if timeout is not None:
            timeout = float(timeout)
        self.timeout = timeout
        self.my_uuid = my_uuid or uuid4()
        if print_uuid:
            sys.stderr.write('%s\n' % self.my_uuid)

        self.prog_name = os.path.basename(sys.argv[0])
        self.auth = auth
        self.session = None
        self.api = None

    def _compat(self, name, default=None):
        """Return server function name.

        Handle back-compat for pre-7.5.0 if relevant.
        """
        # Need to load contact info here to get API version.
        self._load_contact_info()
        if default is None:
            default = name
        return self.COMPAT_MAP[name].get(self.api, default)

    def clear_broadcast(self, **kwargs):
        """Clear broadcast runtime task settings."""
        return self._call_server(
            self._compat('clear_broadcast'), payload=kwargs)

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

    def get_latest_state(self, full_mode):
        """Return latest state of the suite (for the GUI)."""
        self._load_contact_info()
        if self.api == 0:
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

    def get_tasks_by_state(self):
        """Returns a dict containing lists of tasks by state.

        Result in the form:
        {state: [(most_recent_time_string, task_name, point_string), ...]}
        """
        return self._call_server(
            self._compat('get_tasks_by_state'), method=self.METHOD_GET)

    def identify(self):
        """Return suite identity."""
        # Note on compat: Suites on 7.6.0 or above can just call "identify",
        # but has compat for "id/identity".
        return self._call_server('id/identify', method=self.METHOD_GET)

    def put_broadcast(self, **kwargs):
        """Put/set broadcast runtime task settings."""
        return self._call_server(self._compat('put_broadcast'), payload=kwargs)

    def put_command(self, command, **kwargs):
        """Invoke suite command."""
        return self._call_server(
            self._compat('put_command', default='') + command, **kwargs)

    def put_ext_trigger(self, event_message, event_id):
        """Put external trigger."""
        return self._call_server(
            self._compat('put_ext_trigger'),
            event_message=event_message, event_id=event_id)

    def put_message(self, task_id, severity, message):
        """Send task message."""
        func_name = self._compat('put_message')
        if func_name == 'put_message':
            return self._call_server(
                func_name, task_id=task_id, severity=severity, message=message)
        else:  # pre-7.5.0 API compat
            return self._call_server(
                func_name, task_id=task_id, priority=severity, message=message)

    def reset(self):
        """Compat method, does nothing."""
        pass

    def signout(self):
        """Tell server to forget this client."""
        return self._call_server('signout')

    def _call_server(self, function, method=METHOD, payload=None, **kwargs):
        """Build server URL + call it"""
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
        comms_protocol = self.comms_protocol
        if comms_protocol is None:
            # Use standard setting from global configuration
            comms_protocol = glbl_cfg().get(['communication', 'method'])
        url = '%s://%s:%s/%s' % (
            comms_protocol, self.host, self.port, function)
        # If there are any parameters left in the dict after popping,
        # append them to the url.
        if kwargs:
            import urllib
            params = urllib.urlencode(kwargs, doseq=True)
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
        from requests.packages.urllib3.exceptions import InsecureRequestWarning
        warnings.simplefilter("ignore", InsecureRequestWarning)
        if self.session is None:
            self.session = requests.Session()

        if method == self.METHOD_POST:
            session_method = self.session.post
        else:
            session_method = self.session.get
        comms_protocol = url.split(':', 1)[0]  # Can use urlparse?
        username, password, verify = self._get_auth(comms_protocol)
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
        import urllib2
        import ssl
        unverified_context = getattr(ssl, '_create_unverified_context', None)
        if unverified_context is not None:
            ssl._create_default_https_context = unverified_context

        comms_protocol = url.split(':', 1)[0]  # Can use urlparse?
        username, password = self._get_auth(comms_protocol)[0:2]
        auth_manager = urllib2.HTTPPasswordMgrWithDefaultRealm()
        auth_manager.add_password(None, url, username, password)
        auth = urllib2.HTTPDigestAuthHandler(auth_manager)
        opener = urllib2.build_opener(auth, urllib2.HTTPSHandler())
        headers_list = self._get_headers().items()
        if payload:
            payload = json.dumps(payload)
            headers_list.append(('Accept', 'application/json'))
            json_headers = {'Content-Type': 'application/json',
                            'Content-Length': len(payload)}
        else:
            payload = None
            json_headers = {'Content-Length': 0}
        opener.addheaders = headers_list
        req = urllib2.Request(url, payload, json_headers)

        # This is an unpleasant monkey patch, but there isn't an
        # alternative. urllib2 uses POST if there is a data payload
        # but that is not the correct criterion.
        # The difference is basically that POST changes
        # server state and GET doesn't.
        req.get_method = lambda: method
        try:
            response = opener.open(req, timeout=self.timeout)
        except urllib2.URLError as exc:
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
            data = self.srv_files_mgr.load_contact_file(
                self.suite, self.owner, self.host)
            # Port inside "try" block, as it needs a type conversion
            self.port = int(data.get(self.srv_files_mgr.KEY_PORT))
        except (IOError, ValueError, SuiteServiceFileError):
            raise ClientInfoError(self.suite)
        self.host = data.get(self.srv_files_mgr.KEY_HOST)
        self.owner = data.get(self.srv_files_mgr.KEY_OWNER)
        self.comms_protocol = data.get(self.srv_files_mgr.KEY_COMMS_PROTOCOL)
        try:
            self.api = int(data.get(self.srv_files_mgr.KEY_API))
        except (TypeError, ValueError):
            self.api = 0  # Assume cylc-7.5.0 or before


def get_exception_from_html(html_text):
    """Return any content inside a <pre> block with id 'traceback', or None.

    Return e.g. 'abcdef' for text like '<body><pre id="traceback">
    abcdef
    </pre></body>'.

    """
    from HTMLParser import HTMLParser, HTMLParseError

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


if __name__ == '__main__':
    import unittest

    class TestSuiteRuntimeServiceClient(unittest.TestCase):
        """Unit testing class to test the methods in SuiteRuntimeServiceClient
        """
        def test_url_compiler_https(self):
            """Tests that the url parser works for a single url and command
            using https"""
            myclient = SuiteRuntimeServiceClient(
                "test-suite", host=get_host(), port=80,
                comms_protocol="https")
            self.assertEqual(
                'https://%s:80/test_command?apples=False&oranges=True' %
                get_host(),
                myclient._call_server_get_url(
                    "test_command", apples="False", oranges="True"))

        def test_compile_url_compiler_http(self):
            """Test that the url compiler produces a http request when
            http is specified."""
            myclient = SuiteRuntimeServiceClient(
                "test-suite", host=get_host(), port=80,
                comms_protocol="http")
            self.assertEqual(
                'http://%s:80/test_command?apples=False&oranges=True' %
                get_host(),
                myclient._call_server_get_url(
                    "test_command", apples="False", oranges="True"))

        def test_compile_url_compiler_none_specified(self):
            """Test that the url compiler produces a http request when
            none is specified. This should retrieve it from the
            global config."""
            myclient = SuiteRuntimeServiceClient(
                "test-suite", host=get_host(), port=80)
            url = myclient._call_server_get_url(
                "test_command", apples="False", oranges="True")
            # Check that the url has had http (or https) appended
            # to it. (If it does not start with "http*" then something
            # has gone wrong.)
            self.assertTrue(url.startswith("http"))

        def test_get_data_from_url_single_http(self):
            """Test the get data from call_server_impl() function"""
            myclient = SuiteRuntimeServiceClient(
                "dummy-suite", comms_protocol='http')
            ret = myclient.call_server_impl(
                'http://httpbin.org/get', 'GET', None)
            self.assertEqual(ret["url"], "http://httpbin.org/get")

    unittest.main()
