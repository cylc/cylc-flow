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

# Ignore incorrect SSL certificate warning from urllib3 via requests.
warnings.filterwarnings("ignore", "Certificate has no `subjectAltName`")

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

    def call_server_func(self, category, fname, **fargs):
        """Call server_object.fname(*fargs, **fargs)."""
        if self.host is None and self.port is not None:
            self.host = get_hostname()
        try:
            self._load_contact_info()
        except (IOError, ValueError, SuiteServiceFileError):
            raise ConnectionInfoError(self.suite)
        handle_proxies()
        payload = fargs.pop("payload", None)
        method = fargs.pop("method", self.METHOD)
        host = self.host
        if host == "localhost":
            host = get_hostname().split(".")[0]
        url = 'https://%s:%s/%s/%s' % (host, self.port, category, fname)
        if fargs:
            import urllib
            params = urllib.urlencode(fargs, doseq=True)
            url += "?" + params
        return self._get_data_from_url(url, payload, method=method)

    def _get_data_from_url(self, url, json_data, method=None):
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
            return self._get_data_from_url_with_requests(
                url, json_data, method=method)
        return self._get_data_from_url_with_urllib2(
            url, json_data, method=method)

    def _get_data_from_url_with_requests(self, url, json_data, method=None):
        import requests
        username, password = self._get_auth()
        auth = requests.auth.HTTPDigestAuth(username, password)
        if not hasattr(self, "session"):
            self.session = requests.Session()
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
                return self._get_data_from_url_with_requests(
                    url.replace("https:", "http:", 1), json_data)
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
            return ret.json()
        except ValueError:
            return ret.text

    def _get_data_from_url_with_urllib2(self, url, json_data, method=None):
        import json
        import urllib2
        import ssl
        if hasattr(ssl, '_create_unverified_context'):
            ssl._create_default_https_context = ssl._create_unverified_context
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

        # This is an unpleasant monkey patch, but there isn't an alternative.
        # urllib2 uses POST if there is a data payload, but that is not the
        # correct criterion. The difference is basically that POST changes
        # server state and GET doesn't.
        req.get_method = lambda: method
        try:
            response = opener.open(req, timeout=self.timeout)
        except urllib2.URLError as exc:
            if "unknown protocol" in str(exc) and url.startswith("https:"):
                # Server is using http rather than https, for some reason.
                sys.stderr.write(WARNING_NO_HTTPS_SUPPORT.format(exc))
                return self._get_data_from_url_with_urllib2(
                    url.replace("https:", "http:", 1), orig_json_data)
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
            raise ConnectionError(url,
                                  "%s HTTP return code" % response.getcode())
        if self.auth and self.auth[1] != NO_PASSPHRASE:
            self.srv_files_mgr.cache_passphrase(
                self.suite, self.owner, self.host, self.auth[1])
        try:
            return json.loads(response_text)
        except ValueError:
            return response_text

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
