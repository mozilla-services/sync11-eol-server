==========================
Sync1.1 End-of-Life Server
==========================

This application implements a simple memcached-backed server to send
"end-of-life" notifications to Firefox Sync clients.

It provides a tiny portion of the Sync1.1 API as documented here:

    https://docs.services.mozilla.com/storage/apis-1.1.html

It allows reads from "/info/collections", reads/writes to "meta/global" and
"crypto/keys", and deletes to "/storage".  All other requests are rejected
ith a special "513 SERVICE EOL" error that should trigger old sync clients
to show a service-depdecation message to the user.

The allowed requests are designed to work around a client bug, where the EOL
messaging is not shown if it is "trumped" by an error at certain early stages
of the sync sequence.  See the following bug for more details:

    https://bugzilla.mozilla.org/show_bug.cgi?id=1017443

To build in a local virtualenv, simply do::

    make build

To deploy, make sure you've got memcached running and do::

    make serve
