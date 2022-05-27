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

from pathlib import Path
import re
from shlex import split
from subprocess import run
import pytest
import urllib

EXCLUDE = [
    'http://www.gnu.org/licenses/',
    'http://my-site.com/workflows/%(workflow)s/index.html',
    'http://ahost/%(owner)s/notes/%(workflow)s',
    'http://my-site.com/workflows/%(workflow)s/'
]

def get_links():
    searchdir = Path(__file__).parent.parent.parent / 'cylc/flow'
    for file_ in searchdir.rglob('*.py'):
        for url in re.findall(r'(https?:\/\/.*?)[\n\s\>`"\',]', file_.read_text()):
            if url not in EXCLUDE:
                yield {'file': file_, 'url': url}


@pytest.mark.parametrize(
    'link', [
        pytest.param(
            link,
            id=f"{link['url']}"
        )
        for link in get_links()
    ]
)
def test_embedded_url(link):
    try:
        assert urllib.request.urlopen(link['url']).getcode() == 200
    except urllib.error.HTTPError as exc:
        # Allowing 403 - just because a site forbids us doens't mean the
        # link is wrong.
        if exc.code != 403:
            raise Exception(f'{exc} | {link["url"]} | {link["file"]}')



