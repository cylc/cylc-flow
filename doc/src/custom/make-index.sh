#!/bin/bash

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2018 NIWA & British Crown (Met Office) & Contributors.
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

# Install to 'install/' and create an HTML index page to Cylc docs.

set -e

# All paths relative to the '$CYLC_HOME/doc/' directory.
OUT=install
rm -rf $OUT
mkdir -p $OUT
cp src/custom/index.css $OUT
cp -r src/graphics $OUT
CYLC_VERSION=$($(dirname $0)/../../../bin/cylc --version)
INDEX=$OUT/index.html

HTML_DOCS=built-sphinx/

cat > $INDEX <<__END__
<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01//EN">
<html>
  <head>
    <title>Cylc-${CYLC_VERSION}</title>
    <link rel="stylesheet" href="index.css">
  </head>
<body>

<div class="uberpage">
<div class="page">

<h1>Cylc Documentation</h1>

<p>cylc-${CYLC_VERSION}</p>

<div class="rbox">
<h3 style="margin:10px; margin-top:0">Command Help</h3>
<pre class="code">
cylc --help
cylc COMMAND --help
</pre>
<h3 style="margin:10px">Misc.</h3>
<ul>
<li><a href="https://github.com/cylc/cylc/blob/master/CHANGES.md">change log</a></li>
</ul>
</div>

<div class="lbox">
<h3 style="margin:10px">HTML Guides: User Guide & Suite Design Guide</h3>
<ul>
__END__

mkdir -p $OUT/html/
if [[ -f $HTML_DOCS/index.html ]]; then
  cp -r $HTML_DOCS $OUT/html/
  cat >> $INDEX <<__END__
  <li><a href="html/built-sphinx.html">HTML (multi page)</a></li>
__END__
else
    cat >> $INDEX <<__END__
    <li>HTML Guides multi page <i>(not generated)</i></li>
__END__
fi

cat >> $INDEX <<__END__
</ul>
</div>

<div class="lbox">
<h3 style="margin:10px">Online Resources</h3>
<ul>
<li> <a href="http://cylc.github.io/cylc/">Cylc Web Site</a> </li>
<ul>
  <li> <a href="http://cylc.github.io/cylc/documentation.html">Online Documentation</a> </li>
</ul>
<li> <a href="https://github.com/cylc/cylc">Code Repository (GitHub)</a> </li>
</ul>
</div>
</div>

<div class="info">
<p>Document generation:</p>
<ul>
<li> user: <b>
__END__
whoami >> $INDEX
cat >> $INDEX <<__END__
</b> </li>
<li> host: <b>
__END__
hostname -f >> $INDEX
cat >> $INDEX <<__END__
</b> </li>
<li> date: <b>
__END__
date >> $INDEX

cat >> $INDEX <<__END__
</div>
</div>

</body>
</html>
__END__
