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
"""Base classes for web clients."""

import os
import sys
from uuid import uuid4
import warnings

import cylc.flags
from cylc.network import (
    ConnectionError, ConnectionDeniedError, ConnectionInfoError,
    ConnectionTimeout, NO_PASSPHRASE, handle_proxies)
from cylc.owner import is_remote_user, USER
from cylc.suite_srv_files_mgr import (
    SuiteSrvFilesManager, SuiteServiceFileError)
from cylc.suite_host import get_hostname, is_remote_host
from cylc.version import CYLC_VERSION


WARNING_NO_HTTPS_SUPPORT = (
    "WARNING: server has no HTTPS support," +
    " falling back to HTTP: {0}\n"
)


class BaseCommsClient(object):
    """Base class for client-side suite object interfaces."""

    ACCESS_DESCRIPTION = 'private'
    METHOD = 'POST'
    METHOD_POST = 'POST'
    METHOD_GET = 'GET'

    def __init__(self, suite, owner=USER, host=None, port=None, timeout=None,
                 my_uuid=None, print_uuid=False):
        self.suite = suite
        self.owner = owner
        self.host = host
        self.port = port
        if timeout is not None:
            timeout = float(timeout)
        self.timeout = timeout
        self.my_uuid = my_uuid or uuid4()
        if print_uuid:
            print >> sys.stderr, '%s' % self.my_uuid
        self.srv_files_mgr = SuiteSrvFilesManager()
        self.prog_name = os.path.basename(sys.argv[0])
        self.server_cert = None
        self.auth = None

    def _compile_url(self, category, func_dict, host):
        payload = func_dict.pop("payload", None)
        method = func_dict.pop("method", self.METHOD)
        function = func_dict.pop("function", None)
        url = 'https://%s:%s/%s/%s' % (host, self.port, category, function)
        # If there are any parameters left in the dict after popping,
        # append them to the url.
        if func_dict:
            import urllib
            params = urllib.urlencode(func_dict, doseq=True)
            url += "?" + params
        request = {"url": url, "payload": payload, "method": method}
        return request

    def call_server_func(self, category, *func_dicts, **fargs):
        """func_dict is a dictionary of command names (fnames)
        and arguments to that command"""
        # Deal with the case of one func_dict/function name passed
        # by converting them to the generic case: a dictionary of
        # a single function and its function arguments.
        if isinstance(func_dicts[0], str):
            function = func_dicts[0]
            func_dict = {"function": function}
            func_dict.update(fargs)

        if self.host is None and self.port is not None:
            self.host = get_hostname()
        try:
            self._load_contact_info()
        except (IOError, ValueError, SuiteServiceFileError):
            raise ConnectionInfoError(self.suite)
        handle_proxies()
        host = self.host
        if host == "localhost":
            host = get_hostname().split(".")[0]

        http_request_items = []
        try:
            # dictionary containing: url, payload, method
            http_request_item = self._compile_url(category, func_dict, host)
            http_request_items.append(http_request_item)
        except (IndexError, ValueError, AttributeError):
            for f_dict in func_dicts:
                http_request_item = self._compile_url(category, f_dict, host)
                http_request_items.append(http_request_item)
        # returns a list of http returns from the requests
        return self._get_data_from_url(http_request_items)

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
        username, password = self._get_auth()
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
                    verify=self._get_verify(),
                    proxies={},
                    headers=self._get_headers(),
                    auth=auth,
                    timeout=self.timeout
                )
            except requests.exceptions.SSLError as exc:
                if "unknown protocol" in str(exc) and url.startswith("https:"):
                    # Server is using http rather than https, for some reason.
                    sys.stderr.write(WARNING_NO_HTTPS_SUPPORT.format(exc))
                    for item in http_request_items:
                        item['url'] = item['url'].replace("https:", "http:", 1)
                    return self._get_data_from_url_with_requests(
                        http_request_items)
                if cylc.flags.debug:
                    import traceback
                    traceback.print_exc()
                raise ConnectionError(url, exc)
            except requests.exceptions.Timeout as exc:
                if cylc.flags.debug:
                    import traceback
                    traceback.print_exc()
                raise ConnectionTimeout(url, exc)
            except requests.exceptions.RequestException as exc:
                if cylc.flags.debug:
                    import traceback
                    traceback.print_exc()
                raise ConnectionError(url, exc)
            if ret.status_code == 401:
                raise ConnectionDeniedError(url, self.prog_name,
                                            self.ACCESS_DESCRIPTION)
            if ret.status_code >= 400:
                from cylc.network.https.util import get_exception_from_html
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
                raise ConnectionError(url, exc)
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
            orig_json_data = json_data
            username, password = self._get_auth()
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
                    sys.stderr.write(WARNING_NO_HTTPS_SUPPORT.format(exc))
                    for item in http_request_items:
                        item['url'] = item['url'].replace("https:", "http:", 1)
                    return self._get_data_from_url_with_urllib2(
                        http_request_items)
                if cylc.flags.debug:
                    import traceback
                    traceback.print_exc()
                if "timed out" in str(exc):
                    raise ConnectionTimeout(url, exc)
                else:
                    raise ConnectionError(url, exc)
            except Exception as exc:
                if cylc.flags.debug:
                    import traceback
                    traceback.print_exc()
                raise ConnectionError(url, exc)

            if response.getcode() == 401:
                raise ConnectionDeniedError(url, self.prog_name,
                                            self.ACCESS_DESCRIPTION)
            response_text = response.read()
            if response.getcode() >= 400:
                from cylc.network.https.util import get_exception_from_html
                exception_text = get_exception_from_html(response_text)
                if exception_text:
                    sys.stderr.write(exception_text)
                else:
                    sys.stderr.write(response_text)
                raise ConnectionError(
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
            self.auth = ('anon', NO_PASSPHRASE)
            try:
                pphrase = self.srv_files_mgr.get_auth_item(
                    self.srv_files_mgr.FILE_BASE_PASSPHRASE,
                    self.suite, self.owner, self.host, content=True)
            except SuiteServiceFileError:
                pass
            else:
                if pphrase and pphrase != NO_PASSPHRASE:
                    self.auth = ('cylc', pphrase)
        return self.auth

    def _get_headers(self):
        """Return HTTP headers identifying the client."""
        user_agent_string = (
            "cylc/%s prog_name/%s uuid/%s" % (
                CYLC_VERSION, self.prog_name, self.my_uuid
            )
        )
        auth_info = "%s@%s" % (USER, get_hostname())
        return {"User-Agent": user_agent_string,
                "From": auth_info}

    def _get_verify(self):
        """Return the server certificate if possible."""
        if self.server_cert is None:
            try:
                self.server_cert = self.srv_files_mgr.get_auth_item(
                    self.srv_files_mgr.FILE_BASE_SSL_CERT,
                    self.suite, self.owner, self.host)
            except SuiteServiceFileError:
                self.server_cert = False
        return self.server_cert

    def _load_contact_info(self):
        """Obtain suite owner, host, port info.

        Determine host and port using content in port file, unless already
        specified.
        """
        if self.host and self.port:
            return
        data = self.srv_files_mgr.load_contact_file(
            self.suite, self.owner, self.host)
        if not self.host:
            self.host = data.get(self.srv_files_mgr.KEY_HOST)
        if not self.port:
            self.port = int(data.get(self.srv_files_mgr.KEY_PORT))
        if not self.owner:
            self.owner = data.get(self.srv_files_mgr.KEY_OWNER)

    def reset(self, *args, **kwargs):
        pass

    def signout(self, *args, **kwargs):
        pass


class BaseCommsClientAnon(BaseCommsClient):

    """Anonymous access class for clients."""

    ACCESS_DESCRIPTION = 'public'

    def __init__(self, *args, **kwargs):
        # We don't necessarily have certificate access for anon suites.
        warnings.filterwarnings("ignore", "Unverified HTTPS request")
        super(BaseCommsClientAnon, self).__init__(*args, **kwargs)

    def _get_auth(self):
        """Return a user/password Digest Auth."""
        return 'anon', NO_PASSPHRASE

    def _get_verify(self):
        """Other suites' certificates may not be accessible."""
        return False


if __name__ == '__main__':
    import unittest

    class TestBaseCommsClient(unittest.TestCase):
        """Unit testing class to test the methods in BaseCommsClient
        """
        def test_url_compiler(self):
            """Tests that the url parser works for a single url and command"""
            category = 'info'  # Could be any from cylc/network/__init__.py
            host = "localhost"
            func_dict = {"function": "test_command",
                         "apples": "False",
                         "oranges": "True",
                         "method": "GET",
                         "payload": "None"}

            myCommsClient = BaseCommsClient("test-suite", port=80)
            request = myCommsClient._compile_url(category, func_dict, host)
            test_url = ('https://localhost:80/info/test_command'
                        '?apples=False&oranges=True')

            self.assertEqual(request['url'], test_url)
            self.assertEqual(request['payload'], "None")
            self.assertEqual(request['method'], "GET")

        def test_get_data_from_url_single(self):
            """Test the get data from _get_data_from_url() function"""
            myCommsClient = BaseCommsClient("dummy-suite")
            url = "http://httpbin.org/get"
            payload = None
            method = "GET"
            request = [{"url": url, "payload": payload, "method": method}]
            ret = myCommsClient._get_data_from_url(request)
            self.assertEqual(ret['url'], "http://httpbin.org/get")

        def test_get_data_from_url_multiple(self):
            """Tests that the _get_data_from_url() method can
            handle multiple requests in call to the method."""
            myCommsClient = BaseCommsClient("dummy-suite")
            payload = None
            method = "GET"
            request1 = {"url": "http://httpbin.org/get#1",
                        "payload": payload, "method": method}
            request2 = {"url": "http://httpbin.org/get#2",
                        "payload": payload, "method": method}
            request3 = {"url": "http://httpbin.org/get#3",
                        "payload": payload, "method": method}

            rets = myCommsClient._get_data_from_url([request1,
                                                     request2, request3])

            for i in range(2):
                self.assertEqual(rets[i]['url'], "http://httpbin.org/get")

    unittest.main()
