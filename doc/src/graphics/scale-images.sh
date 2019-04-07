#!/bin/bash

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

# Scale png images down *if they are wider than 600px* for use in the
# HTML User Guide.

set -e

# The images in png/scaled/ are used in the html user guide; they are
# created by scaling the originals in png/orig/, and may need to be
# re-scaled if we ever change the html user guide page width.

# The scaled images are now version controlled rather than treated as a
# derived product, because they have to be stored in the gh-pages branch
# for the online documentation, and re-creating them seems to result in 
# "different" binary files each time.
mkdir -p png/scaled
for PNG in "png/orig/"*; do
    if [[ ! -f png/scaled/$PNG ]]; then
        echo "scaling $PNG"
        convert -resize '600>' "png/orig/$PNG" "png/scaled/$PNG"
    fi
done
