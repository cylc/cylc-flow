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

import fnmatch
from pathlib import Path
import re
from time import sleep
import pytest
import urllib

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


@pytest.mark.linkcheck
@pytest.mark.parametrize('link', get_links())
def test_embedded_url(link):
    """Check links in the source code are not broken.

    TIP: use `--dist=load` when running pytest to enable parametrized tests
    to run in parallel
    """
    try:
        urllib.request.urlopen(link).getcode()
    except urllib.error.HTTPError:
        # Sleep and retry to reduce risk of flakiness:
        sleep(10)
        try:
            urllib.request.urlopen(link).getcode()
        except urllib.error.HTTPError as exc:
            # Allowing 403 - just because a site forbids us doesn't mean the
            # link is wrong.
            if exc.code != 403:
                raise Exception(f'{exc} | {link}') from None
