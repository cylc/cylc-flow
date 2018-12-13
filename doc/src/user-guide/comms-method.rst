.. _Communication:

Communication Method
====================

Cylc suite server programs and clients (commands, cylc GUI, task messaging)
communicate via particular ports using the HTTPS protocol, secured
by HTTP Digest Authentication using the suite's 20-random-character
private passphrase and private SSL certificate.

This is enabled via the included-in-cylc cherrypy library (for the
server) and either the Python requests library (if available) or
the built-in Python libraries for the clients.

All suites are entirely isolated from one another.


.. insert vertical whitespace else sidebar menu overhangs short page (ugly)

|
|
|
|
|
|
|
|
|
|
|
|
|
|
|
|
