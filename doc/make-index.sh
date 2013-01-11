#!/bin/bash

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

# This script generates an HTML index page linking to cylc
# documentation. It is intended to be executed automatically 
# during the document generation process (see Makefile). The resulting
# index file will link to whichever documentation formats have been
# generated (PDF and/or HTML single page and/or HTML multi-page).
# It can however be executed manually from within the doc directory.

echo
echo "Generating document index"
echo

CYLC_VERSION=$($(dirname $0)/../bin/cylc --version)
INDEX=index.html

cat > $INDEX <<END
<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01//EN">
<html>
		<head>
				<title>Cylc Documentation Index</title>
				<link rel="stylesheet" href="index.css">
		</head>

<body>

<div class="uberpage">
<div class="page">

<div style="float:right">
<b>
END

echo $CYLC_VERSION >> $INDEX

cat >> $INDEX <<END
</b>
</div>

<h1>Cylc Documentation</h1>

<p>Run the <code>cylc documentation</code> command to get here 
(see <code>cylc doc --help</code>).<p>


<div class="rbox">
<h3 style="margin:10px">Command Help</h3>
<pre class="code">
cylc --help
cylc COMMAND --help
</pre>
</div>

<div class="lbox">
<h3 style="margin:10px">User Guide</h3>
<p>For this cylc version: 
END
echo $CYLC_VERSION >> $INDEX

cat >> $INDEX <<END
</p>
<ul>
END

if [[ -f cug.pdf ]]; then
    cat >> $INDEX <<END
<li> <a href="cug.pdf">PDF format</a> </li>
END
else
    cat >> $INDEX <<END
    <li>PDF format <i>(not generated)</i></li>
END
fi

if [[ -f cug1.html ]]; then
    cat >> $INDEX <<END
<li> <a href="cug1.html">HTML single-page</a> </li>
END
else
    cat >> $INDEX <<END
    <li> HTML single page <i>(not generated)</i></li>
END

fi

if [[ -f cug.html ]]; then
    cat >> $INDEX <<END
<li> <a href="cug.html">HTML multi-page</a> </li>
END
else
    cat >> $INDEX <<END
    <li> HTML multi-page <i>(not generated)</i></li>
END
fi

cat >> $INDEX <<END
</ul>
</div>

<div class="lbox">
<h3 style="margin:10px">Internet</h3>
<p>For the latest cylc release</p>
<ul>
<li> <a href="http://cylc.github.com/cylc/#">Project Homepage</a> </li>
<li> <a href="http://cylc.github.com/cylc/#documentation">Online Documentation</a> </li>
<li> <a href="https://github.com/cylc/cylc">Github Source Repository</a> </li>
</ul>
</div>
</div>

<div class="info">
<p>Document generation:</p>
<ul>
<li> user: <b>
END
whoami >> $INDEX
cat >> $INDEX <<END
</b> </li>
<li> host: <b>
END
hostname -f >> $INDEX
cat >> $INDEX <<END
</b> </li>
<li> date: <b>
END
date >> $INDEX

cat >> $INDEX <<END
</div>
</div>

</body>
</html>
END

