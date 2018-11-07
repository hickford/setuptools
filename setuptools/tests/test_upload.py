import mock
import os
import re

from distutils import log
from distutils.version import StrictVersion

import pytest
import six

from setuptools.command.upload import upload
from setuptools.dist import Distribution


def _parse_upload_body(body):
    boundary = u'\r\n----------------GHSKFJDLGDS7543FJKLFHRE75642756743254'
    entries = []
    name_re = re.compile(u'^Content-Disposition: form-data; name="([^\"]+)"')

    for entry in body.split(boundary):
        pair = entry.split(u'\r\n\r\n')
        if not len(pair) == 2:
            continue

        key, value = map(six.text_type.strip, pair)
        m = name_re.match(key)
        if m is not None:
            key = m.group(1)

        entries.append((key, value))

    return entries


@pytest.fixture
def patched_upload(tmpdir):
    class Fix:
        def __init__(self, cmd, urlopen):
            self.cmd = cmd
            self.urlopen = urlopen

        def __iter__(self):
            return iter((self.cmd, self.urlopen))

        def get_uploaded_metadata(self):
            request = self.urlopen.call_args_list[0][0][0]
            body = request.data.decode('utf-8')
            entries = dict(_parse_upload_body(body))

            return entries

    class ResponseMock(mock.Mock):
        def getheader(self, name, default=None):
            """Mocked getheader method for response object"""
            return {
                'content-type': 'text/plain; charset=utf-8',
            }.get(name.lower(), default)

    with mock.patch('setuptools.command.upload.urlopen') as urlopen:
        urlopen.return_value = ResponseMock()
        urlopen.return_value.getcode.return_value = 200
        urlopen.return_value.read.return_value = b''

        content = os.path.join(str(tmpdir), "content_data")

        with open(content, 'w') as f:
            f.write("Some content")

        dist = Distribution()
        dist.dist_files = [('sdist', '3.7.0', content)]

        cmd = upload(dist)
        cmd.announce = mock.Mock()
        cmd.username = 'user'
        cmd.password = 'hunter2'

        yield Fix(cmd, urlopen)


class TestUploadTest:
    def test_upload_metadata(self, patched_upload):
        cmd, patch = patched_upload

        # Set the metadata version to 2.1
        cmd.distribution.metadata.metadata_version = '2.1'

        # Run the command
        cmd.ensure_finalized()
        cmd.run()

        # Make sure we did the upload
        patch.assert_called_once()

        # Make sure the metadata version is correct in the headers
        entries = patched_upload.get_uploaded_metadata()
        assert entries['metadata_version'] == '2.1'


    def test_warns_deprecation(self):
        dist = Distribution()
        dist.dist_files = [(mock.Mock(), mock.Mock(), mock.Mock())]

        cmd = upload(dist)
        cmd.upload_file = mock.Mock()
        cmd.announce = mock.Mock()

        cmd.run()

        cmd.announce.assert_called_once_with(
            "WARNING: Uploading via this command is deprecated, use twine to "
            "upload instead (https://pypi.org/p/twine/)",
            log.WARN
        )

    def test_warns_deprecation_when_raising(self):
        dist = Distribution()
        dist.dist_files = [(mock.Mock(), mock.Mock(), mock.Mock())]

        cmd = upload(dist)
        cmd.upload_file = mock.Mock()
        cmd.upload_file.side_effect = Exception
        cmd.announce = mock.Mock()

        with pytest.raises(Exception):
            cmd.run()

        cmd.announce.assert_called_once_with(
            "WARNING: Uploading via this command is deprecated, use twine to "
            "upload instead (https://pypi.org/p/twine/)",
            log.WARN
        )
