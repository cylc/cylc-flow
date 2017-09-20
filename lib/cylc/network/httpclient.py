#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2017 NIWA
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
from uuid import uuid4
import warnings

from cylc.exceptions import CylcError
import cylc.flags
from cylc.network import NO_PASSPHRASE
from cylc.suite_host import get_suite_host, get_user
from cylc.suite_srv_files_mgr import (
    SuiteSrvFilesManager, SuiteServiceFileError)
from cylc.unicode_util import utf8_enforce
from cylc.version import CYLC_VERSION


# Note: This was renamed from ConnectionError to ClientError. ConnectionError
# is a built-in exception in Python 3.
class ClientError(Exception):

    """An error raised when the client cannot connect."""

    MESSAGE = "Cannot connect: %s: %s"

    def __str__(self):
        return self.MESSAGE % (self.args[0], self.args[1])


class ClientDeniedError(ClientError):

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
        self.port = port
        self.srv_files_mgr = SuiteSrvFilesManager()
        self.comms_protocol = comms_protocol
        if timeout is not None:
            timeout = float(timeout)
        self.timeout = timeout
        self.my_uuid = my_uuid or uuid4()
        if print_uuid:
            print >> sys.stderr, '%s' % self.my_uuid

        self.prog_name = os.path.basename(sys.argv[0])
        self.auth = auth

    def clear_broadcast(self, **kwargs):
        """Clear broadcast runtime task settings."""
        return self._call_server_func('clear_broadcast', payload=kwargs)

    def expire_broadcast(self, **kwargs):
        """Expire broadcast runtime task settings."""
        return self._call_server_func('expire_broadcast', **kwargs)

    def get_broadcast(self, **kwargs):
        """Return broadcast settings."""
        return self._call_server_func(
            'get_broadcast', method=self.METHOD_GET, **kwargs)

    def get_gui_summary(self, full_mode):
        """Return summary and other info for GUI."""
        return self._call_server_func(
            'get_gui_summary', method=self.METHOD_GET, full_mode=full_mode)

    def get_suite_state_summary(self):
        """Return the global, task, and family summary data structures."""
        return utf8_enforce(self._call_server_func(
            'get_suite_state_summary', method=self.METHOD_GET))

    def get_tasks_by_state(self):
        """Returns a dict containing lists of tasks by state.

        Result in the form:
        {state: [(most_recent_time_string, task_name, point_string), ...]}
        """
        return self._call_server_func(
            'get_tasks_by_state', method=self.METHOD_GET)

    def get_info(self, command, *args, **kwargs):
        """Return suite info."""
        kwargs['method'] = self.METHOD_GET
        return self._call_server_func(command, *args, **kwargs)

    def identify(self):
        """Return suite identity."""
        return self._call_server_func('identify', method=self.METHOD_GET)

    def put_broadcast(self, **kwargs):
        """Put/set broadcast runtime task settings."""
        return self._call_server_func('put_broadcast', payload=kwargs)

    def put_command(self, command, **kwargs):
        """Invoke suite command."""
        return self._call_server_func(command, **kwargs)

    def put_ext_trigger(self, event_message, event_id):
        """Put external trigger."""
        return self._call_server_func(
            'put_ext_trigger', event_message=event_message, event_id=event_id)

    def put_message(self, task_id, priority, message):
        """Send task message."""
        return self._call_server_func(
            'put_message', task_id=task_id, priority=priority, message=message)

    def reset(self, *args, **kwargs):
        """Compat method, does nothing."""
        pass

    def signout(self, *args, **kwargs):
        """Tell server to forget this client."""
        return self._call_server_func('signout')

    def _get_comms_from_suite_contact_file(self):
        """Find out the communications protocol (http/https) from the
        suite contact file."""
        try:
            comms_prtcl = self.srv_files_mgr.get_auth_item(
                self.srv_files_mgr.KEY_COMMS_PROTOCOL,
                self.suite, content=True)
            if comms_prtcl is None or comms_prtcl == "":
                raise TypeError("Comms protocol is not in suite contact file")
            else:
                return comms_prtcl
        except (AttributeError, KeyError, TypeError, ValueError):
            raise KeyError("No suite contact info for comms protocol found")

    @staticmethod
    def _get_comms_from_global_config():
        """Find out the communications protocol (http/https) from the
        user' global config file."""
        from cylc.cfgspec.globalcfg import GLOBAL_CFG
        comms_methods = GLOBAL_CFG.get(['communication', 'method'])
        # Set the comms method
        if "https" in comms_methods:
            return "https"
        elif "http" in comms_methods:
            return "http"
        else:
            # Something has gone very wrong here
            # possibly user set bad value in global config
            raise CylcError(
                "Communications protocol "
                "\"{0}\" invalid."
                " (protocol set in global config.)".format(comms_methods))

    def _compile_url(self, func_dict, host, comms_protocol=None):
        """Build request URL."""
        payload = func_dict.pop("payload", None)
        method = func_dict.pop("method", self.METHOD)
        function = func_dict.pop("function", None)

        if comms_protocol is None:
            try:
                protocol_prefix = self._get_comms_from_suite_contact_file()
            except (KeyError, TypeError, SuiteServiceFileError):
                protocol_prefix = self._get_comms_from_global_config()
        elif comms_protocol is not None:
            protocol_prefix = comms_protocol
        else:
            raise CylcError("Unable to detect suite communication protocol")
        url = protocol_prefix + '://%s:%s/%s' % (host, self.port, function)
        # If there are any parameters left in the dict after popping,
        # append them to the url.
        if func_dict:
            import urllib
            params = urllib.urlencode(func_dict, doseq=True)
            url += "?" + params
        return {"url": url, "payload": payload, "method": method}

    def _call_server_func(self, *func_dicts, **fargs):
        """func_dict is a dictionary of command names (fnames)
        and arguments to that command"""
        # Deal with the case of one func_dict/function name passed
        # by converting them to the generic case: a dictionary of
        # a single function and its function arguments.
        if isinstance(func_dicts[0], str):
            func_dict = {"function": func_dicts[0]}
            func_dict.update(fargs)
        else:
            func_dict = None

        try:
            self._load_contact_info()
        except (IOError, ValueError, SuiteServiceFileError):
            raise ClientInfoError(self.suite)
        host = self.host
        if host == 'localhost':
            host = get_suite_host()

        http_request_items = []
        try:
            # dictionary containing: url, payload, method
            http_request_items.append(self._compile_url(
                func_dict, host, self.comms_protocol))
        except (IndexError, ValueError, AttributeError):
            for f_dict in func_dicts:
                http_request_items.append(self._compile_url(
                    f_dict, host, self.comms_protocol))
        # Remove proxy settings from environment for now
        environ = {}
        for key in ("http_proxy", "https_proxy"):
            val = os.environ.pop(key, None)
            if val:
                environ[key] = val
        # Returns a list of http returns from the requests
        try:
            return self._get_data_from_url(http_request_items)
        finally:
            os.environ.update(environ)

    def _get_data_from_url(self, http_request_items):
        requests_ok = True
        try:
            import requests
        except ImportError:
            requests_ok = False
        else:
            version = [int(_) for _ in requests.__version__.split(".")]
            if version < [2, 4, 2]:
                requests_ok = False
        if requests_ok:
            return self._get_data_from_url_with_requests(http_request_items)
        return self._get_data_from_url_with_urllib2(http_request_items)

    def _get_data_from_url_with_requests(self, http_request_items):
        import requests
        from requests.packages.urllib3.exceptions import InsecureRequestWarning
        warnings.simplefilter("ignore", InsecureRequestWarning)
        username, password, verify = self._get_auth()
        auth = requests.auth.HTTPDigestAuth(username, password)
        if not hasattr(self, "session"):
            self.session = requests.Session()

        http_return_items = []
        for http_request_item in http_request_items:
            method = http_request_item['method']
            url = http_request_item['url']
            json_data = http_request_item['payload']
            if method is None:
                method = self.METHOD
            if method == self.METHOD_POST:
                session_method = self.session.post
            else:
                session_method = self.session.get
            try:
                ret = session_method(
                    url,
                    json=json_data,
                    verify=verify,
                    proxies={},
                    headers=self._get_headers(),
                    auth=auth,
                    timeout=self.timeout
                )
            except requests.exceptions.SSLError as exc:
                if "unknown protocol" in str(exc) and url.startswith("https:"):
                    # Server is using http rather than https, for some reason.
                    sys.stderr.write(self.ERROR_NO_HTTPS_SUPPORT.format(exc))
                    raise CylcError(
                        "Cannot issue commands over unsecured http.")
                if cylc.flags.debug:
                    import traceback
                    traceback.print_exc()
                raise ClientError(url, exc)
            except requests.exceptions.Timeout as exc:
                if cylc.flags.debug:
                    import traceback
                    traceback.print_exc()
                raise ClientTimeout(url, exc)
            except requests.exceptions.RequestException as exc:
                if cylc.flags.debug:
                    import traceback
                    traceback.print_exc()
                raise ClientError(url, exc)
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
                    import traceback
                    traceback.print_exc()
                raise ClientError(url, exc)
            if self.auth and self.auth[1] != NO_PASSPHRASE:
                self.srv_files_mgr.cache_passphrase(
                    self.suite, self.owner, self.host, self.auth[1])
            try:
                ret = ret.json()
                http_return_items.append(ret)
            except ValueError:
                ret = ret.text
                http_return_items.append(ret)
        # Return a single http return or a list of them if multiple
        return (http_return_items if len(http_return_items) > 1
                else http_return_items[0])

    def _get_data_from_url_with_urllib2(self, http_request_items):
        import json
        import urllib2
        import ssl
        if hasattr(ssl, '_create_unverified_context'):
            ssl._create_default_https_context = ssl._create_unverified_context

        http_return_items = []
        for http_request_item in http_request_items:
            method = http_request_item['method']
            url = http_request_item['url']
            json_data = http_request_item['payload']
            if method is None:
                method = self.METHOD
            username, password = self._get_auth()[0:2]
            auth_manager = urllib2.HTTPPasswordMgrWithDefaultRealm()
            auth_manager.add_password(None, url, username, password)
            auth = urllib2.HTTPDigestAuthHandler(auth_manager)
            opener = urllib2.build_opener(auth, urllib2.HTTPSHandler())
            headers_list = self._get_headers().items()
            if json_data:
                json_data = json.dumps(json_data)
                headers_list.append(('Accept', 'application/json'))
                json_headers = {'Content-Type': 'application/json',
                                'Content-Length': len(json_data)}
            else:
                json_data = None
                json_headers = {'Content-Length': 0}
            opener.addheaders = headers_list
            req = urllib2.Request(url, json_data, json_headers)

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
                    import traceback
                    traceback.print_exc()
                if "timed out" in str(exc):
                    raise ClientTimeout(url, exc)
                else:
                    raise ClientError(url, exc)
            except Exception as exc:
                if cylc.flags.debug:
                    import traceback
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
                raise ClientError(
                    url,
                    "%s HTTP return code" % response.getcode())
            if self.auth and self.auth[1] != NO_PASSPHRASE:
                self.srv_files_mgr.cache_passphrase(
                    self.suite, self.owner, self.host, self.auth[1])

            try:
                http_return_items.append(json.loads(response_text))
            except ValueError:
                http_return_items.append(response_text)
        # Return a single http return or a list of them if multiple
        return (http_return_items if len(http_return_items) > 1
                else http_return_items[0])

    def _get_auth(self):
        """Return a user/password Digest Auth."""
        if self.auth is None:
            self.auth = self.ANON_AUTH
            try:
                pphrase = self.srv_files_mgr.get_auth_item(
                    self.srv_files_mgr.FILE_BASE_PASSPHRASE,
                    self.suite, self.owner, self.host, content=True)
                server_cert = self.srv_files_mgr.get_auth_item(
                    self.srv_files_mgr.FILE_BASE_SSL_CERT,
                    self.suite, self.owner, self.host)
            except SuiteServiceFileError:
                pass
            else:
                if pphrase and pphrase != NO_PASSPHRASE:
                    self.auth = ('cylc', pphrase, server_cert)
        return self.auth

    def _get_headers(self):
        """Return HTTP headers identifying the client."""
        user_agent_string = (
            "cylc/%s prog_name/%s uuid/%s" % (
                CYLC_VERSION, self.prog_name, self.my_uuid
            )
        )
        auth_info = "%s@%s" % (get_user(), get_suite_host())
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
            self.host = get_suite_host()
            return
        data = self.srv_files_mgr.load_contact_file(
            self.suite, self.owner, self.host)
        if not self.host:
            self.host = data.get(self.srv_files_mgr.KEY_HOST)
        if not self.port:
            self.port = int(data.get(self.srv_files_mgr.KEY_PORT))
        if not self.owner:
            self.owner = data.get(self.srv_files_mgr.KEY_OWNER)
        if not self.comms_protocol:
            self.comms_protocol = data.get(
                self.srv_files_mgr.KEY_COMMS_PROTOCOL)


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
            host = "localhost"
            func_dict = {"function": "test_command",
                         "apples": "False",
                         "oranges": "True",
                         "method": "GET",
                         "payload": "None"}

            myclient = SuiteRuntimeServiceClient("test-suite", port=80)
            request_https = myclient._compile_url(func_dict, host, "https")

            test_url_https = (
                'https://localhost:80/test_command'
                '?apples=False&oranges=True')

            self.assertEqual(request_https['url'], test_url_https)
            self.assertEqual(request_https['payload'], "None")
            self.assertEqual(request_https['method'], "GET")

        def test_compile_url_compiler_http(self):
            """Test that the url compiler produces a http request when
            http is specified."""
            host = "localhost"
            func_dict = {"function": "test_command",
                         "apples": "False",
                         "oranges": "True",
                         "method": "GET",
                         "payload": "None"}

            myclient = SuiteRuntimeServiceClient("test-suite", port=80)
            request_http = myclient._compile_url(func_dict, host, "http")
            test_url_http = (
                'http://localhost:80/test_command'
                '?apples=False&oranges=True')

            self.assertEqual(request_http['url'], test_url_http)
            self.assertEqual(request_http['payload'], "None")
            self.assertEqual(request_http['method'], "GET")

        def test_compile_url_compiler_none_specified(self):
            """Test that the url compiler produces a http request when
            none is specified. This should retrieve it from the
            global config."""
            host = "localhost"
            func_dict = {"function": "test_command",
                         "apples": "False",
                         "oranges": "True",
                         "method": "GET",
                         "payload": "None"}

            myclient = SuiteRuntimeServiceClient("test-suite", port=80)
            request_http = myclient._compile_url(func_dict, host)

            # Check that the url has had http (or https) appended
            # to it. (If it does not start with "http*" then something
            # has gone wrong.)
            self.assertTrue(request_http['url'].startswith("http"))

        def test_get_data_from_url_single_http(self):
            """Test the get data from _get_data_from_url() function"""
            myclient = SuiteRuntimeServiceClient("dummy-suite")
            url = "http://httpbin.org/get"
            payload = None
            method = "GET"
            request = [{"url": url, "payload": payload, "method": method}]
            ret = myclient._get_data_from_url(request)
            self.assertEqual(ret['url'], "http://httpbin.org/get")

        def test_get_data_from_url_multiple(self):
            """Tests that the _get_data_from_url() method can
            handle multiple requests in call to the method."""
            myclient = SuiteRuntimeServiceClient("dummy-suite")
            payload = None
            method = "GET"
            request1 = {"url": "http://httpbin.org/get#1",
                        "payload": payload, "method": method}
            request2 = {"url": "http://httpbin.org/get#2",
                        "payload": payload, "method": method}
            request3 = {"url": "http://httpbin.org/get#3",
                        "payload": payload, "method": method}

            rets = myclient._get_data_from_url([request1, request2, request3])

            for i in range(2):
                self.assertEqual(rets[i]['url'], "http://httpbin.org/get")

    unittest.main()
