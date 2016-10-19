#!/bin/bash
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

# Test authentication - privilege 'identity'.

. $(dirname $0)/test_header

if ! wget --version 1>'/dev/null' 2>&1; then
    skip_all '"wget" command not available'
fi

set_test_number 6

install_suite "${TEST_NAME_BASE}" basic

TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${SUITE_NAME}"

cylc run "${SUITE_NAME}"
unset CYLC_CONF_PATH

# Wait for first task 'foo' to fail.
cylc suite-state "${SUITE_NAME}" --task=foo --status=failed --cycle=1 \
    --interval=1 --max-polls=10 || exit 1

PORT=$(cylc ping -v "${SUITE_NAME}" | cut -d':' -f 2)
SUITE_RUN_DIR="$(cylc get-global-config --print-run-dir)/${SUITE_NAME}"
if grep -q "^WARNING: no HTTPS support" "${SUITE_RUN_DIR}/log/suite/err"; then
    URL="http://localhost:${PORT}"
else
    URL="https://localhost:${PORT}"
fi

TEST_NAME="${TEST_NAME_BASE}-wget-json"
export http_proxy= https_proxy=
run_ok "${TEST_NAME}" wget "$URL/broadcast/index?form=json" --no-check-certificate --user=cylc \
    --password=$(cat "${TEST_DIR}/${SUITE_NAME}/passphrase") -O index
TEST_NAME="${TEST_NAME_BASE}-print-json"
run_ok "${TEST_NAME}" python -c "import json, pprint, sys; pprint.pprint(json.loads(sys.stdin.read()))" <index
cmp_ok "${TEST_NAME}.stdout" <<__OUT__
[{u'argdoc': u'(point_strings=None, namespaces=None, cancel_settings=None)',
  u'doc': u'Clear settings globally, or for listed namespaces and/or points.\n\nUsually accepts a JSON payload formatted as the kwargs dict\nwould be for this method.\n\nKwargs:\n\n* point_strings - list or None\n    List of target point strings to clear. None or empty list means\n    clear all point strings.\n* namespaces - list or None\n    List of target namespaces. None or empty list means clear all\n    namespaces.\n* cancel_settings - list or NOne\n    List of particular settings to clear. None or empty list means\n    clear all settings.\n\nReturn a tuple (modified_settings, bad_options), where:\n* modified_settings is similar to the return value of the "put" method,\n  but for removed settings.\n* bad_options is a dict in the form:\n      {"point_strings": ["20020202", ..."], ...}\n  The dict is only populated if there are options not associated with\n  previous broadcasts. The keys can be:\n  * point_strings: a list of bad point strings.\n  * namespaces: a list of bad namespaces.\n  * cancel: a list of tuples. Each tuple contains the keys of a bad\n    setting.',
  u'name': u'clear'},
 {u'argdoc': u'(cutoff=None)',
  u'doc': u'Clear all settings targeting cycle points earlier than cutoff.\n\nExample URLs:\n\n* /expire\n* /expire?cutoff=20100504T1200Z\n\nKwargs:\n\n* cutoff - string or None\n    If cutoff is a point string, expire all broadcasts < cutoff\n    If cutoff is None, expire all broadcasts.',
  u'name': u'expire'},
 {u'argdoc': u'(task_id=None)',
  u'doc': u'Retrieve all broadcast variables that target a given task ID.\n\nExample URLs:\n\n* /get\n* /get?task_id=:failed\n* /get?task_id=20200202T0000Z/*\n* /get?task_id=foo.20101225T0600Z\n\nKwargs:\n\n* task_id - string or None\n    If given, return the broadcasts set for this task_id spec.\n    If None, return all currently set broadcasts.',
  u'name': u'get'},
 {u'argdoc': u"(form='html')",
  u'doc': u"Return the methods (=sub-urls) within this class.\n\nExample URL:\n\n* https://host:port/CLASS/\n\nKwargs:\n\n* form - string\n    form can be either 'html' (default) or 'json' for easily\n    machine readable output.",
  u'name': u'index'},
 {u'argdoc': u'(point_strings=None, namespaces=None, settings=None, not_from_client=False)',
  u'doc': u'Add new broadcast settings (server side interface).\n\nExample URL:\n\n* /put (plus JSON payload)\n\nUsually accepts a JSON payload formatted as the kwargs dict\nwould be for this method.\n\nKwargs:\n\n* point_strings - list\n    List of applicable cycle points for these settings. Can\n    be [\'*\'] to cover all cycle points.\n* namespaces - list\n    List of applicable namespaces. Can also be ["root"].\n* settings - list\n    List of setting key value dictionaries to apply. For\n    example, [{"pre-script": "sleep 10"}].\n* not_from_client - boolean\n    If True, do not attempt to read in JSON - use keyword\n    arguments instead. If False (default), read in JSON.\n\nReturn a tuple (modified_settings, bad_options) where:\n  modified_settings is list of modified settings in the form:\n    [("20200202", "foo", {"script": "true"}, ...]\n  bad_options is as described in the docstring for self.clear().',
  u'name': u'put'}]
__OUT__

TEST_NAME="${TEST_NAME_BASE}-wget-html"
run_ok "${TEST_NAME}" wget "$URL/broadcast/index" --no-check-certificate --user=cylc \
    --password=$(cat "${TEST_DIR}/${SUITE_NAME}/passphrase") -O "${TEST_NAME_BASE}-index.html"
cmp_ok "${TEST_NAME_BASE}-index.html" <<__OUT__
<html><head>
<title>Cylc Comms API for BroadcastServer</title></head>
<h1>BroadcastServer</h1>
<h2>clear</h2>
<p>clear(point_strings=None, namespaces=None, cancel_settings=None)</p>
<pre>Clear settings globally, or for listed namespaces and/or points.

Usually accepts a JSON payload formatted as the kwargs dict
would be for this method.

Kwargs:

* point_strings - list or None
    List of target point strings to clear. None or empty list means
    clear all point strings.
* namespaces - list or None
    List of target namespaces. None or empty list means clear all
    namespaces.
* cancel_settings - list or NOne
    List of particular settings to clear. None or empty list means
    clear all settings.

Return a tuple (modified_settings, bad_options), where:
* modified_settings is similar to the return value of the "put" method,
  but for removed settings.
* bad_options is a dict in the form:
      {"point_strings": ["20020202", ..."], ...}
  The dict is only populated if there are options not associated with
  previous broadcasts. The keys can be:
  * point_strings: a list of bad point strings.
  * namespaces: a list of bad namespaces.
  * cancel: a list of tuples. Each tuple contains the keys of a bad
    setting.</pre>
<h2>expire</h2>
<p>expire(cutoff=None)</p>
<pre>Clear all settings targeting cycle points earlier than cutoff.

Example URLs:

* /expire
* /expire?cutoff=20100504T1200Z

Kwargs:

* cutoff - string or None
    If cutoff is a point string, expire all broadcasts < cutoff
    If cutoff is None, expire all broadcasts.</pre>
<h2>get</h2>
<p>get(task_id=None)</p>
<pre>Retrieve all broadcast variables that target a given task ID.

Example URLs:

* /get
* /get?task_id=:failed
* /get?task_id=20200202T0000Z/*
* /get?task_id=foo.20101225T0600Z

Kwargs:

* task_id - string or None
    If given, return the broadcasts set for this task_id spec.
    If None, return all currently set broadcasts.</pre>
<h2>index</h2>
<p>index(form='html')</p>
<pre>Return the methods (=sub-urls) within this class.

Example URL:

* https://host:port/CLASS/

Kwargs:

* form - string
    form can be either 'html' (default) or 'json' for easily
    machine readable output.</pre>
<h2>put</h2>
<p>put(point_strings=None, namespaces=None, settings=None, not_from_client=False)</p>
<pre>Add new broadcast settings (server side interface).

Example URL:

* /put (plus JSON payload)

Usually accepts a JSON payload formatted as the kwargs dict
would be for this method.

Kwargs:

* point_strings - list
    List of applicable cycle points for these settings. Can
    be ['*'] to cover all cycle points.
* namespaces - list
    List of applicable namespaces. Can also be ["root"].
* settings - list
    List of setting key value dictionaries to apply. For
    example, [{"pre-script": "sleep 10"}].
* not_from_client - boolean
    If True, do not attempt to read in JSON - use keyword
    arguments instead. If False (default), read in JSON.

Return a tuple (modified_settings, bad_options) where:
  modified_settings is list of modified settings in the form:
    [("20200202", "foo", {"script": "true"}, ...]
  bad_options is as described in the docstring for self.clear().</pre>
</html>
__OUT__

# Stop and purge the suite.
cylc stop --max-polls=10 --interval=1 "${SUITE_NAME}"
purge_suite "${SUITE_NAME}"
exit
