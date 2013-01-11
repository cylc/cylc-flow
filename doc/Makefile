#!/usr/bin/make -f

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2013 Hilary Oliver, NIWA
#C: 
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.

CYLC=$(dir $(abspath $(lastword $(MAKEFILE_LIST))))../bin/cylc

.PHONY: all commands clean tidy html html-multi html-single pdf index

# All the main phony targets depend initially on 'commands', which
# regenerates commands.tex only if the command usage help has changed.
# The real targets cannot have phony prerequisites as that would make
# them execute every time. Consequently: DO NOT USE THE REAL TARGETS
# DIRECTLY OR commands.tex WILL NOT BE REGENERATED WHEN IT SHOULD BE.
#   E.g. use 'make pdf' NOT 'make cug.pdf'.
# The index is regenerated for every real target; this is OK because 
# it is fast, and the index links to all the final documents found.

all: commands pdf html

html: commands html-multi html-single

html-multi: commands cug.html

html-single: commands cug1.html

pdf: commands cug.pdf

# just for standalone use: "make index"
index:
	./make-index.sh

commands:
	./make-commands.sh

cug.html: commands.tex cug-html.tex cug.tex
	$(CYLC) -v > cylc-version.txt
	htlatex cug-html.tex "cug-html.cfg,xhtml,3,next"
	mv cug-html.html $@
	rm -f cug-html.{4ct,4tc,aux,dvi,idv,lg,log,tmp,toc,xref}
	./make-index.sh

cug1.html: commands.tex cug-html.tex cug.tex
	$(CYLC) -v > cylc-version.txt
	htlatex cug-html.tex "cug-html.cfg,xhtml,fn-in" ""
	mv cug-html.html $@
	rm -f cug-html.{4ct,4tc,aux,dvi,idv,lg,log,tmp,toc,xref}
	./make-index.sh

cug.pdf: commands.tex cug-pdf.tex cug.tex
	$(CYLC) -v > cylc-version.txt
	pdflatex cug-pdf.tex
	pdflatex cug-pdf.tex
	pdflatex cug-pdf.tex
	rm -f cug-pdf.{lof,log,out,toc}
	mv cug-pdf.pdf $@
	./make-index.sh

# delete all generated files:
clean:
	rm -rf *.aux\
        command-usage\
        commands.tex\
        cug.html\
        cug1.html\
        cug-html.{4ct,4tc,aux,css,dvi,idv,lg,log,tmp,toc,xref}\
        cug-html*.html\
        cug-pdf.{lof,log,out,pdf,toc}\
        cug.pdf\
        index.html \
        cylc-version.txt\

# delete all intermediate files:
tidy:
	rm -rf *.aux\
        command-usage\
        commands.tex\
        cug-html.{4ct,4tc,aux,css,dvi,idv,lg,log,tmp,toc,xref}\
        cug-pdf.{lof,log,out,pdf,toc}\
        cylc-version.txt\

