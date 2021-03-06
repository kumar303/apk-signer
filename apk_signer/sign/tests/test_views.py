from contextlib import contextmanager
from cStringIO import StringIO
import hashlib
import tempfile

from django.conf import settings
from django.core.urlresolvers import reverse

import mock
from nose.tools import eq_

from apk_signer.base.tests import TestCase


class SignTestBase(TestCase):

    def setUp(self):
        self.key_path = '/path/to/unsigned/file.apk'
        self.signed_path = '/path/to/signed/file.apk'
        self.file_hash = 'maybe'

        p = mock.patch('apk_signer.sign.views.signer')
        self.signer = p.start()
        self.addCleanup(p.stop)

        tmp = tempfile.NamedTemporaryFile()
        self.signer.sign.return_value = tmp
        self.addCleanup(tmp.close)

    def data(self):
        return {
            'unsigned_apk_s3_path': self.key_path,
            'unsigned_apk_s3_hash': self.file_hash,
            'signed_apk_s3_path': self.signed_path,
            'apk_id': 'id_derived_from_manifest',
        }

    def post(self, data=None):
        data = data or self.data()
        return self.client.post(reverse('sign'), data=data)


class TestSignView(SignTestBase):

    def setUp(self):
        super(TestSignView, self).setUp()
        p = mock.patch('apk_signer.sign.views.storage')
        self.stor = p.start()
        self.addCleanup(p.stop)
        self.stor.bucket_key_exists.return_value = True

    def test_missing_s3_path(self):
        data = self.data()
        del data['unsigned_apk_s3_path']
        eq_(self.post(data).status_code, 400)

    def test_missing_s3_hash(self):
        data = self.data()
        del data['unsigned_apk_s3_hash']
        eq_(self.post(data).status_code, 400)

    def test_missing_s3_signed_path(self):
        data = self.data()
        del data['signed_apk_s3_path']
        eq_(self.post(data).status_code, 400)

    def test_missing_apk_id(self):
        data = self.data()
        del data['apk_id']
        eq_(self.post(data).status_code, 400)

    def test_non_existant_key(self):
        self.stor.bucket_key_exists.return_value = False
        eq_(self.post().status_code, 400)
        self.stor.bucket_key_exists.assert_called_with(
            settings.S3_APK_BUCKET, self.key_path)


class TestSignedStorage(SignTestBase):

    @contextmanager
    def buf(self, content):
        yield StringIO(content)

    def setUp(self):
        super(TestSignedStorage, self).setUp()

        p = mock.patch('apk_signer.sign.views.storage')
        storage = p.start()
        self.addCleanup(p.stop)
        self.get_apk = storage.get_apk
        self.put_signed_apk = storage.put_signed_apk

        self.stor = storage
        self.stor.signed_apk_url.return_value = '<url>'

        content = '<pretend this is APK data>'
        self.file_hash = hashlib.sha256(content).hexdigest()
        buf = self.buf(content)
        self.get_apk.return_value = buf

    def test_fetch_ok(self):
        self.post()
        self.get_apk.assert_called_with(self.key_path)

    def test_put_ok(self):
        url = '<apk_url>'
        self.stor.signed_apk_url.return_value = url
        res = self.json(self.post())
        self.put_signed_apk.assert_called_with(mock.ANY, self.signed_path)
        eq_(res['signed_apk_s3_url'], url)

    def test_hash_fail(self):
        data = self.data()
        data['unsigned_apk_s3_hash'] = 'fail'
        eq_(self.post(data).status_code, 400)
