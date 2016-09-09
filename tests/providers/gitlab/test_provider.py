import pytest

import io
import os
import json
import base64
import hashlib
from http import client

import aiohttpretty

from waterbutler.core import streams
from waterbutler.core import exceptions
from waterbutler.core.path import WaterButlerPath
from waterbutler.core.provider import build_url

from waterbutler.providers.gitlab import GitLabProvider
from waterbutler.providers.gitlab import settings as gitlab_settings
from waterbutler.providers.gitlab.provider import GitLabPath
from waterbutler.providers.gitlab.metadata import GitLabRevision
from waterbutler.providers.gitlab.metadata import GitLabFileTreeMetadata
from waterbutler.providers.gitlab.metadata import GitLabFolderTreeMetadata
from waterbutler.providers.gitlab.metadata import GitLabFileContentMetadata
from waterbutler.providers.gitlab.metadata import GitLabFolderContentMetadata

@pytest.fixture
def auth():
    return {
        'name': 'cat',
        'email': 'cat@cat.com',
    }


@pytest.fixture
def credentials():
    return {'token': 'naps'}


@pytest.fixture
def settings():
    return {
        'owner': 'cat',
        'repo': 'food',
        'repo_id': '123',
        'base_url': 'http://base.url',
        'view_url': 'http://view.url',
    }


@pytest.fixture
def repo_metadata():
    return {
        'full_name': 'octocat/Hello-World',
        'settings': {
            'push': False,
            'admin': False,
            'pull': True
        }
    }

@pytest.fixture
def provider(auth, credentials, settings, repo_metadata):
    provider = GitLabProvider(auth, credentials, settings)
    return provider

class TestHelpers:
    def test_build_repo_url(self, provider, settings):
        expected = 'http://base.url/projects/123/contents'
        assert provider.build_repo_url('contents') == expected

class TestMetadata:
    @pytest.mark.asyncio
    @pytest.mark.aiohttpretty
    async def test_metadata_file_with_default_ref(self, provider):
        path = '/folder1/folder2/file'

        waterbutler_path = GitLabPath(path)

        url = 'http://base.url/projects/123/repository/files?ref=master&file_path=folder1/folder2/file'

        aiohttpretty.register_json_uri('GET', url, body={
                'file_name': 'file',
                'blob_id': 'abc123',
                'commit_id': 'xxxyyy',
                'file_path': '/folder1/folder2/file',
                'size': '123'
            }
        )

        result = await provider.metadata(waterbutler_path)

        assert result.name == 'file'
        assert result.size == '123'

    @pytest.mark.asyncio
    @pytest.mark.aiohttpretty
    async def test_metadata_file_with_ref(self, provider):
        path = '/folder1/folder2/file'

        waterbutler_path = GitLabPath(path)

        url = 'http://base.url/projects/123/repository/files?ref=my-branch&file_path=folder1/folder2/file'

        aiohttpretty.register_json_uri('GET', url, body={
                'file_name': 'file',
                'blob_id': 'abc123',
                'commit_id': 'xxxyyy',
                'file_path': '/folder1/folder2/file',
                'size': '123'
            }
        )

        result = await provider.metadata(waterbutler_path, 'my-branch')

        assert result.name == 'file'
        assert result.size == '123'

    @pytest.mark.asyncio
    @pytest.mark.aiohttpretty
    async def test_metadata_folder(self, provider):
        path = '/folder1/folder2/folder3/'

        waterbutler_path = GitLabPath(path)

        url = 'http://base.url/projects/123/repository/tree?path=folder1/folder2/folder3/'

        aiohttpretty.register_json_uri('GET', url, body=[
            {
                'id': '123',
                'type': 'tree',
                'name': 'my folder'
            },
            {
                'id': '1234',
                'type': 'file',
                'name': 'my file'
            }
        ])

        result = await provider.metadata(waterbutler_path)

        assert isinstance(result[0], GitLabFolderContentMetadata)
        assert result[0].name == 'my folder'

        assert result[1].name == 'my file'
        assert isinstance(result[1], GitLabFileContentMetadata)

    @pytest.mark.asyncio
    @pytest.mark.aiohttpretty
    async def test_metadata_folder_with_sha(self, provider):
        path = '/folder1/folder2/folder3/'

        waterbutler_path = GitLabPath(path)

        result = await provider.metadata(waterbutler_path, ref='4b825dc642cb6eb9a060e54bf8d69288fbee4904')

        assert result == None

    @pytest.mark.asyncio
    @pytest.mark.aiohttpretty
    async def test_metadata_folder_recursive(self, provider):
        path = '/folder1/folder2/folder3/'

        waterbutler_path = GitLabPath(path)

        result = await provider.metadata(waterbutler_path, recursive=True)

        assert result == None

    @pytest.mark.asyncio
    @pytest.mark.aiohttpretty
    async def test_metadata_folder_with_no_dict_response(self, provider):
        path = '/folder1/folder2/folder3/'

        waterbutler_path = GitLabPath(path)

        url = 'http://base.url/projects/123/repository/tree?path=folder1/folder2/folder3/'

        aiohttpretty.register_json_uri('GET', url, body={})

        with pytest.raises(exceptions.MetadataError) as exc:
            await provider.metadata(waterbutler_path)
