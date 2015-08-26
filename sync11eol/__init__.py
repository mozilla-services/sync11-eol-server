# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import os
import hmac
import json
import time
import hashlib

from pyramid.response import Response
from pyramid.view import view_config

from mozsvc.config import get_configurator, SettingsDict
from mozsvc.storage.mcclient import MemcachedClient


# The default memcached TTL, in seconds.
# We use two days, which should be long enough for multi-device clusters to
# process a migration via the /meta/fxa_credentials sentinel, but not so long
# as to be problemantic in production.
DEFAULT_MEMCACHED_TTL = 2 * 24 * 60 * 60

# Field defaults to use in the EOL json message.
DEFAULT_EOL_MESSAGE = "The sync1.1 service has been shut down"
DEFAULT_EOL_URL = "https://support.mozilla.org/kb/" + \
                  "how-to-update-to-the-new-firefox-sync"


ALLOWED_BSO_NAMES = (
    "meta/global",
    "meta/fxa_credentials",
    "crypto/keys",
)


def get_timestamp():
    """Get the current time, as an integer.

    For this simple service we use integer timestamps only, to avoid having
    to deal with precision/decimals/etc.
    """
    return int(time.time())


def mc_key(request, name):
    """Calculate the key under which a user's BSO is stored in memcached.

    This function provides a primitive kind of "authentication" by hashing
    the user's credentials into the name of the key.  The only way to get
    the data back is to provide the same credentials.
    """
    secret_key = request.registry.settings["sync11eol.secret_key"]
    username = request.matchdict["username"]
    authz = request.headers.get("Authorization", "")
    if authz:
        authz = authz.rsplit(None, 1)[-1]
    authz_hash = hmac.new(secret_key, authz, hashlib.sha256).hexdigest()
    return "/".join((username, authz_hash, name))


def mc_get(request, name):
    """Helper to get info for a user's BSO out of memcached."""
    mc = request.registry["sync11eol.mcclient"]
    key = mc_key(request, name)
    return mc.get(key)


def mc_set(request, name, value):
    """Helper to set info for a user's BSO in memcached."""
    registry = request.registry
    mc = registry["sync11eol.mcclient"]
    key = mc_key(request, name)
    ttl = registry.settings.get("memcached.ttl", DEFAULT_MEMCACHED_TTL)
    return mc.set(key, value, time=ttl)


def mc_del(request, name):
    """Helper to delete info for a user's BSO in memcached."""
    mc = request.registry["sync11eol.mcclient"]
    key = mc_key(request, name)
    return mc.delete(key)


def get_bso(request, name):
    """Get the data stored for a user's BSO in memcached."""
    bso = mc_get(request, name)
    if bso is None:
        return Response(status=404)
    r = Response(json.dumps(bso), status=200)
    r.headers["Content-Type"] = "application/json"
    r.headers["X-Weave-Timestamp"] = str(get_timestamp())
    return r


def put_bso(request, name):
    """set the data stored for a user's BSO in memcached."""
    now = get_timestamp()
    try:
        bso = json.loads(request.body)
        bso["modified"] = now
    except (ValueError, TypeError):
        return Response("0", status="400")
    mc_set(request, name, bso)
    r = Response(str(now), status=200)
    r.headers["Content-Type"] = "application/json"
    r.headers["X-Weave-Timestamp"] = str(now)
    return r


@view_config(route_name="metaglobal", request_method="GET")
def get_meta_global(request):
    """Read the stored meta/global BSO."""
    return get_bso(request, "meta/global")


@view_config(route_name="metaglobal", request_method="PUT")
def put_meta_global(request):
    """Write the stored meta/global BSO."""
    return put_bso(request, "meta/global")


@view_config(route_name="metafxa", request_method="GET")
def get_meta_fxa_credentials(request):
    """Read the stored meta/fxa_credentials BSO."""
    return get_bso(request, "meta/fxa_credentials")


@view_config(route_name="metafxa", request_method="PUT")
def put_meta_fxa_credentials(request):
    """Write the stored meta/fxa_credentials BSO."""
    return put_bso(request, "meta/fxa_credentials")


@view_config(route_name="cryptokeys", request_method="GET")
def get_crypto_keys(request):
    """Read the stored crypto/keys BSO."""
    return get_bso(request, "crypto/keys")


@view_config(route_name="cryptokeys", request_method="PUT")
def put_crypto_keys(request):
    """Write the stored crypto/keys BSO."""
    return put_bso(request, "crypto/keys")


@view_config(route_name="collections", renderer="json")
def get_info_collections(request):
    """Get the collection timestamps for /info/collections.

    Since we only store the "meta" and "crypto" collections, these are
    the only two that will ever be reported.
    """
    info = {}
    for name in ALLOWED_BSO_NAMES:
        bso = mc_get(request, name)
        if bso is not None:
            collection = name.split("/")[0]
            info[collection] = max(info.get(collection, 0), bso["modified"])
    return info


@view_config(route_name="storage", request_method="DELETE")
def del_storage(request):
    """Delete all the stored data for the user."""
    for name in ALLOWED_BSO_NAMES:
        mc_del(request, name)
    r = Response("0", status=200)
    r.headers["Content-Type"] = "application/json"
    r.headers["X-Weave-Timestamp"] = str(get_timestamp())
    return r


@view_config(route_name="other")
@view_config(route_name="metaglobal", request_method="DELETE")
@view_config(route_name="metafxa", request_method="DELETE")
@view_config(route_name="cryptokeys", request_method="DELETE")
def hard_eol(request):
    """Send a 513 SERVICE EOL response.

    This is the special response that triggers EOL messaging in the client
    app.  We send it on every request that we possibly can, excluding only
    those for which the error-handling route is buggy.
    """
    settings = request.registry.settings
    response = Response("0")
    response.status = "513 SERVICE EOL"
    response.content_type = "application/json"
    response.headers["X-Weave-Alert"] = json.dumps({
        "code": "hard-eol",
        "url": settings.get("sync11eol.url", DEFAULT_EOL_URL),
        "message": settings.get("sync11eol.message", DEFAULT_EOL_MESSAGE),
    })
    return response


def includeme(config):
    config.include("cornice")
    config.include("mozsvc")

    prefix = "/{api:1.0|1|1.1}/{username:[a-zA-Z0-9._-]{1,100}}"
    config.add_route("collections", prefix + "/info/collections")
    config.add_route("metaglobal", prefix + "/storage/meta/global")
    config.add_route("metafxa", prefix + "/storage/meta/fxa_credentials")
    config.add_route("cryptokeys", prefix + "/storage/crypto/keys")
    config.add_route("storage", prefix + "/storage")
    config.add_route("other", prefix + "*other")
    config.scan('sync11eol')

    settings = config.registry.settings
    if not isinstance(settings, SettingsDict):
        settings = SettingsDict(settings)

    mc = MemcachedClient(**settings.getsection("memcached"))
    config.registry["sync11eol.mcclient"] = mc

    if "sync11eol.secret_key" not in config.registry.settings:
        config.registry.settings["sync11eol.secret_key"] = os.urandom(32)


def main(global_config, **settings):
    config = get_configurator(global_config, **settings)
    config.include(includeme)
    return config.make_wsgi_app()
