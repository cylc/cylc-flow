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
"""Base classes for web clients."""

import os
import sys
from uuid import uuid4
import warnings

# Ignore incorrect SSL certificate warning from urllib3 via requests.
warnings.filterwarnings("ignore", "Certificate has no `subjectAltName`")

from cylc.exceptions import PortFileError
import cylc.flags
from cylc.network import (
    ConnectionError, ConnectionDeniedError, NO_PASSPHRASE, handle_proxies)
from cylc.owner import is_remote_user, USER
from cylc.registration import RegistrationDB, PassphraseError
from cylc.suite_host import get_hostname, is_remote_host
from cylc.suite_env import CylcSuiteEnv, CylcSuiteEnvLoadError
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

    def __init__(self, suite, owner=USER, host=None, timeout=None,
                 port=None, db=None, my_uuid=None, print_uuid=False):
        self.suite = suite
        self.host = host
        self.owner = owner
        if timeout is not None:
            timeout = float(timeout)
        self.timeout = timeout
        self.port = port
        self.my_uuid = my_uuid or uuid4()
        if print_uuid:
            print >> sys.stderr, '%s' % self.my_uuid
        self.reg_db = RegistrationDB(db)
        self.prog_name = os.path.basename(sys.argv[0])

    def call_server_func(self, category, fname, **fargs):
        """Call server_object.fname(*fargs, **fargs)."""
        if self.host is None or self.port is None:
            self._load_contact_info()
        handle_proxies()
        payload = fargs.pop("payload", None)
        method = fargs.pop("method", self.METHOD)
        host = self.host
        if not self.host.split(".")[0].isdigit():
            host = self.host.split(".")[0]
        if host == "localhost":
            host = get_hostname().split(".")[0]
        url = 'https://%s:%s/%s/%s' % (
            host, self.port, category, fname
        )
        if fargs:
            import urllib
            params = urllib.urlencode(fargs, doseq=True)
            url += "?" + params
        return self.get_data_from_url(url, payload, method=method)

    def get_data_from_url(self, url, json_data, method=None):
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
            return self.get_data_from_url_with_requests(
                url, json_data, method=method)
        return self.get_data_from_url_with_urllib2(
            url, json_data, method=method)

    def get_data_from_url_with_requests(self, url, json_data, method=None):
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
                return self.get_data_from_url_with_requests(
                    url.replace("https:", "http:", 1), json_data)
            if cylc.flags.debug:
                import traceback
                traceback.print_exc()
            raise ConnectionError(url, exc)
        except Exception as exc:
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
        except Exception as exc:
            if cylc.flags.debug:
                import traceback
                traceback.print_exc()
            raise ConnectionError(url, exc)
        try:
            return ret.json()
        except ValueError:
            return ret.text

    def get_data_from_url_with_urllib2(self, url, json_data, method=None):
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
        # urllib2 uses POST iff there is a data payload, but that is not the
        # correct criterion. The difference is basically that POST changes
        # server state and GET doesn't.
        req.get_method = lambda: method
        try:
            response = opener.open(req, timeout=self.timeout)
        except urllib2.URLError as exc:
            if "unknown protocol" in str(exc) and url.startswith("https:"):
                # Server is using http rather than https, for some reason.
                sys.stderr.write(WARNING_NO_HTTPS_SUPPORT.format(exc))
                return self.get_data_from_url_with_urllib2(
                    url.replace("https:", "http:", 1), orig_json_data)
            if cylc.flags.debug:
                import traceback
                traceback.print_exc()
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
        try:
            return json.loads(response_text)
        except ValueError:
            return response_text

    def _get_auth(self):
        """Return a user/password Digest Auth."""
        self.pphrase = self.reg_db.load_passphrase(
            self.suite, self.owner, self.host)
        if self.pphrase:
            self.reg_db.cache_passphrase(
                self.suite, self.owner, self.host, self.pphrase)
        if self.pphrase is None:
            return 'anon', NO_PASSPHRASE
        return 'cylc', self.pphrase

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
        if not hasattr(self, "server_cert"):
            try:
                self.server_cert = self.reg_db.load_item(
                    self.suite, self.owner, self.host, "certificate")
            except PassphraseError:
                return False
        return self.server_cert

    def _load_contact_info(self):
        """Obtain URL info.

        Determine host and port using content in port file, unless already
        specified.

        """
        if self.host and self.port:
            return
        if 'CYLC_SUITE_RUN_DIR' in os.environ:
            # Looks like we are in a running task job, so we should be able to
            # use "cylc-suite-env" file under the suite running directory
            try:
                suite_env = CylcSuiteEnv.load(
                    self.suite, os.environ['CYLC_SUITE_RUN_DIR'])
            except CylcSuiteEnvLoadError:
                if cylc.flags.debug:
                    import traceback
                    traceback.print_exc()
            else:
                self.host = suite_env.suite_host
                self.port = suite_env.suite_port
                self.owner = suite_env.suite_owner
        if self.host is None or self.port is None:
            self._load_port_file()

    def _load_port_file(self):
        """Load port, host, etc from port file."""
        # GLOBAL_CFG is expensive to import, so only load on demand
        from cylc.cfgspec.globalcfg import GLOBAL_CFG
        port_file_path = os.path.join(
            GLOBAL_CFG.get(['communication', 'ports directory']), self.suite)
        out = ""
        if is_remote_host(self.host) or is_remote_user(self.owner):
            # Only load these modules on demand, as they may be expensive
            import shlex
            from subprocess import Popen, PIPE
            ssh_tmpl = str(GLOBAL_CFG.get_host_item(
                'remote shell template', self.host, self.owner))
            ssh_tmpl = ssh_tmpl.replace(' %s', '')
            user_at_host = ''
            if self.owner:
                user_at_host = self.owner + '@'
            if self.host:
                user_at_host += self.host
            else:
                user_at_host += 'localhost'
            r_port_file_path = port_file_path.replace(
                os.environ['HOME'], '$HOME')
            command = shlex.split(ssh_tmpl) + [
                user_at_host, 'cat', r_port_file_path]
            proc = Popen(command, stdout=PIPE, stderr=PIPE)
            out, err = proc.communicate()
            ret_code = proc.wait()
            if ret_code:
                if cylc.flags.debug:
                    print >> sys.stderr, {
                        "code": ret_code,
                        "command": command,
                        "stdout": out,
                        "stderr": err}
                if self.port is None:
                    raise PortFileError(
                        "Port file '%s:%s' not found - suite not running?." %
                        (user_at_host, r_port_file_path))
        else:
            try:
                out = open(port_file_path).read()
            except IOError:
                if self.port is None:
                    raise PortFileError(
                        "Port file '%s' not found - suite not running?." %
                        (port_file_path))
        lines = out.splitlines()
        if self.port is None:
            try:
                self.port = int(lines[0])
            except (IndexError, ValueError):
                raise PortFileError(
                    "ERROR, bad content in port file: %s" % port_file_path)
        if self.host is None:
            if len(lines) >= 2:
                self.host = lines[1].strip()
            else:
                self.host = get_hostname()

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
