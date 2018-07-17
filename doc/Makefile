#!/usr/bin/make -f

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2018 NIWA & British Crown (Met Office) & contributors
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

.PHONY: all cug sdg cug-pdf cug-html clean install installclean

all: sdg cug install

sdg: src/suite-design-guide/document.pdf

cug: cug-pdf cug-html
	
cug-pdf: src/cylc-user-guide/pdf/cug-pdf.pdf

cug-html: src/cylc-user-guide/html/single/cug-html.html \
          src/cylc-user-guide/html/multi/cug-html.html

src/suite-design-guide/document.pdf:
	cd src/suite-design-guide && $(MAKE)

src/cylc-user-guide/pdf/cug-pdf.pdf:
	cd src/cylc-user-guide && $(MAKE) pdf

src/cylc-user-guide/html/single/cug-html.html:
	cd src/cylc-user-guide && $(MAKE) html-single

src/cylc-user-guide/html/multi/cug-html.html:
	cd src/cylc-user-guide && $(MAKE) html-multi

install:
	./src/make-index.sh

clean:
	cd src/suite-design-guide && $(MAKE) clean
	cd src/cylc-user-guide && $(MAKE) clean

installclean:
	rm -r install
