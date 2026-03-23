# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.
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

"""Check links inserted into internal documentation.

Reason for doing this here:
- Some links don't appear to be being picked up by Cylc-doc linkcheck.
- As we have more links it's worth checking them here, rather than waiting
  for them to show up in Cylc.
"""

import os
import re
import pytest
import fnmatch

from time import sleep
from pathlib import Path
from urllib import request
from urllib.error import HTTPError

EXCLUDE = [
    r'*//www.gnu.org/licenses/',
    r'*//my-site.com/*',
    r'*//ahost/%(owner)s/notes/%(workflow)s',
    r'*//web.archive.org/*'
]


def get_links():
    searchdir = Path(__file__).parent.parent.parent / 'cylc' / 'flow'
    return sorted({
        url
        for file_ in searchdir.rglob('*.py')
        for url in re.findall(
            r'(https?:\/\/.*?)[\n\s\>`"\',]', file_.read_text()
        )
        if not any(
            fnmatch.fnmatch(url, pattern) for pattern in EXCLUDE
        )
    })


def make_request(link):
    """Make an HTTP request, using GITHUB_TOKEN for GitHub URLs if available.

    The GITHUB_TOKEN environment variable contains a GitHub Actions token.
    This is used to authenticate the workflow requests to github.com, which
    helps avoid rate limiting (unauthenticated requests are limited to 60/hour,
    authenticated to 5000/hour).
    """
    req = request.Request(link)
    github_token = os.environ.get('GITHUB_TOKEN')
    if github_token and 'github.com' in link:
        req.add_header('Authorization', f'token {github_token}')
    return request.urlopen(req).getcode()


@pytest.mark.linkcheck
@pytest.mark.parametrize('link', get_links())
def test_embedded_url(link):
    """Check links in the source code are not broken.

    TIP: use `--dist=load` when running pytest to enable parametrized tests
    to run in parallel
    """
    try:
        make_request(link)
    except HTTPError:
        # Sleep and retry to reduce risk of flakiness:
        sleep(10)
        try:
            make_request(link)
        except HTTPError as exc:
            # Allowing 403 (forbidden) & 429 (rate-limited) as the link
            # is probably valid, but we are blocked.
            if exc.code in {403, 429}:
                pytest.skip(f'{exc} | {link}')
            raise Exception(f'{exc} | {link}')
