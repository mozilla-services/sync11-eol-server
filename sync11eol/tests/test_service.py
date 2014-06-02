# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import os
import json
import unittest

from webtest import TestApp
from pyramid import testing

from cornice.tests.support import CatchErrors


class TestSync11EOLService(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()
        self.config.include("sync11eol")
        wsgiapp = self.config.make_wsgi_app()
        wsgiapp = CatchErrors(wsgiapp)
        self.app = TestApp(wsgiapp)
        self.username = os.urandom(10).encode("hex")
        self.root = '/1.1/' + self.username

    def test_info_collections(self):
        # /info/collections tracks metaglobal and cryptokeys, but
        # no other collections.  It is created on demand.
        r = self.app.get(self.root + '/info/collections')
        self.assertEquals(r.json, {})
        self.app.put(self.root + '/storage/meta/global', '{}')
        r = self.app.get(self.root + '/info/collections')
        self.assertEquals(r.json.keys(), ['meta'])
        self.app.put(self.root + '/storage/crypto/keys', '{}')
        r = self.app.get(self.root + '/info/collections')
        self.assertEquals(sorted(r.json.keys()), ['crypto', 'meta'])
        # The other /info URLs give the EOL response.
        self.app.get(self.root + '/info/collections_count', status=513)

    def test_meta_global(self):
        # /meta/global can be read and written to, but not deleted.
        self.app.get(self.root + '/storage/meta/global', status=404)
        r = self.app.put(self.root + '/storage/meta/global', '{}')
        ts = float(r.body)
        r = self.app.get(self.root + '/storage/meta/global')
        self.assertEquals(r.json['modified'], ts)
        self.app.delete(self.root + '/storage/meta/global', status=513)

    def test_crypto_keys(self):
        # /crypto/keys can be read and written to, but not deleted.
        self.app.get(self.root + '/storage/crypto/keys', status=404)
        r = self.app.put(self.root + '/storage/crypto/keys', '{}')
        ts = float(r.body)
        r = self.app.get(self.root + '/storage/crypto/keys')
        self.assertEquals(r.json['modified'], ts)
        self.app.delete(self.root + '/storage/crypto/keys', status=513)

    def test_storage_delete(self):
        # A DELETE /storage will appear to succeed
        self.app.delete(self.root + '/storage')

    def test_other(self):
        # All other parts of the API return the EOL response.
        r = self.app.get(self.root + '/storage/bookmarks', status=513)
        alert = json.loads(r.headers["X-Weave-Alert"])
        self.assertEquals(sorted(alert.keys()), ["code", "message", "url"])
        self.assertEquals(alert["code"], "hard-eol")
        self.app.post(self.root + '/storage/history', '[{}]', status=513)
        self.app.delete(self.root + '/storage/tabs', status=513)
        self.app.get(self.root + '/meta/globular', status=513)

    def test_expected_device_flow(self):
        # The client checks /meta/global and finds it missing.
        self.app.get(self.root + '/storage/meta/global', status=404)
        # It resets the account and uploads metaglobal and cryptokeys.
        self.app.delete(self.root + '/storage')
        self.app.put(self.root + '/storage/meta/global', '{}')
        self.app.put(self.root + '/storage/crypto/keys', '{}')
        # It fetches the data it just uploaded, to sanity-check.
        r = self.app.get(self.root + '/info/collections')
        self.assertEqual(sorted(r.json.keys()), ['crypto', 'meta'])
        self.app.get(self.root + '/storage/crypto/keys')
        # It goes to actually sync, and sees the EOL error.
        self.app.post(self.root + '/storage/bookmarks', '[{}]', status=513)