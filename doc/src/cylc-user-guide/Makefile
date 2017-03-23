#!/usr/bin/make -f

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

.PHONY: all pdf html html-multi html-single clean

DEPS := $(shell ./scripts/get-deps.sh)
CYLC = ../../../bin/cylc

all: $(DEPS)

pdf: pdf/cug-pdf.pdf

html: html-multi html-single

html-multi: html/multi/cug-html.html

html-single: html/single/cug-html.html

commands.tex: $(CYLC)-*
	./scripts/make-commands.sh

html/multi/cug-html.html: commands.tex cug-html.tex cug.tex suiterc.tex siterc.tex gcylcrc.tex cug-html.cfg
	- ./scripts/make-html.sh multi

html/single/cug-html.html: commands.tex cug-html.tex cug.tex suiterc.tex siterc.tex gcylcrc.tex cug-html.cfg
	- ./scripts/make-html.sh single

pdf/cug-pdf.pdf: commands.tex cug-pdf.tex cug.tex suiterc.tex siterc.tex gcylcrc.tex
	- ./scripts/make-pdf.sh

clean:
	rm -rf pdf html commands.tex cylc-version.txt
