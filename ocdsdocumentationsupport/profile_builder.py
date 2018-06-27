import csv
import json
import logging
import os
import re
from collections import OrderedDict
from io import BytesIO, StringIO
from zipfile import ZipFile

import json_merge_patch
import requests
from ocdsextensionregistry import ExtensionRegistry

logger = logging.getLogger('oc_dsdocumentationsupport')


def _append_extension(name, content, extension_name):
    """
    Returns a list of rows from the content, adding an Extension column and removing deprecated codes.
    """
    rows = []

    for row in csv.DictReader(StringIO(content)):
        if row.pop('Deprecated', None):
            logger.info('... skipping deprecated code {} in {}'.format(row['Code'], name))
            continue

        row['Extension'] = extension_name
        rows.append(row)

    return rows


def _json_loads(data):
    """
    Loads JSON data, preserving order.
    """
    return json.loads(data, object_pairs_hook=OrderedDict)


class ProfileBuilder:
    def __init__(self, standard_version, extension_versions, registry_base_url=None):
        """
        Accepts an OCDS version and a dictionary of extension identifiers and versions, and initializes a reader of the
        extension registry.
        """
        self.standard_version = standard_version
        self.extension_versions = extension_versions
        self._file_cache = {}

        # Allows setting the registry URL to e.g. a pull request, when working on a profile.
        if not registry_base_url:
            registry_base_url = 'https://raw.githubusercontent.com/open-contracting/extension_registry/master/'

        self.registry = ExtensionRegistry(registry_base_url + 'extension_versions.csv')

    def extensions(self):
        """
        Returns the matching extension versions from the registry.
        """
        for identifier, version in self.extension_versions.items():
            yield self.registry.get(id=identifier, version=version)

    def release_schema_patch(self):
        """
        Returns the consolidated release schema patch.
        """
        profile_patch = OrderedDict()

        # Replaces `null` with sentinel values, to preserve the null'ing of fields by extensions in the final patch.
        for extension in self.extensions():
            data = re.sub(r':\s*null\b', ': "REPLACE_WITH_NULL"', extension.remote('release-schema.json'))
            json_merge_patch.merge(profile_patch, _json_loads(data))

        return _json_loads(json.dumps(profile_patch).replace('"REPLACE_WITH_NULL"', 'null'))

    def patched_release_schema(self):
        """
        Returns the patched release schema.
        """
        data = self.get_standard_file_contents('release-schema.json')
        return json_merge_patch.merge(_json_loads(data), self.release_schema_patch())

    def codelist_patches(self):
        """
        Returns the rows of the codelist patches and new codelists within the extensions. Adds an Extension column and
        removes deprecated codes.
        """
        codelists = {}
        originals = {}

        for extension in self.extensions():
            # standard-maintenance-scripts validates the "codelists" field in extension.json. An extension is not
            # guaranteed to offer a download URL, which is the only other way to get codelists.
            for name in json.loads(extension.remote('extension.json')).get('codelists', []):
                content = extension.remote('codelists/' + name)
                rows = _append_extension(name, content, extension.metadata['name']['en'])

                # New codelists and codelist replacements should be identical across extensions. Codelist additions and
                # removals are merged across extensions.
                if name in codelists:
                    if name.startswith(('+', '-')):
                        codelists[name].extend(rows)
                    else:
                        assert originals[name] == content, 'codelist {} is different across extensions'.format(name)
                else:
                    codelists[name] = rows
                    originals[name] = content

        # If a codelist replacement (name.csv) is consistent with additions (+name.csv) and removals (-name.csv), then
        # the latter should be removed. This avoids profile authors having to instruct the profile builder to ignore
        # specific codelists. In other words, the expectations are that:
        #
        # * A codelist replacement shouldn't omit added codes.
        # * A codelist replacement shouldn't include removed codes.
        # * If codes are added after a codelist is replaced, this should result in duplicate codes.
        # * If codes are removed after a codelist is replaced, this should result in no change.
        #
        # If these expectations are not met, an error is raised.
        for name in list(codelists.keys()):
            if name.startswith(('+', '-')) and name[1:] in codelists:
                codes = [row['Code'] for row in codelists[name[1:]]]
                if name.startswith('+'):
                    for row in codelists[name]:
                        code = row['Code']
                        assert code in codes, '{} added by {}, but not in {}'.format(code, name, name[1:])
                    logger.info('{0} has the codes added by {1}, ignoring {1}'.format(name[1:], name))
                else:
                    for row in codelists[name]:
                        code = row['Code']
                        assert code not in codes, '{} removed by {}, but in {}'.format(code, name, name[1:])
                    logger.info('{0} has no codes removed by {1}, ignoring {1}'.format(name[1:], name))
                del codelists[name]

        return codelists

    def patched_codelists(self):
        """
        Returns the rows of the patched codelists and new codelists from the extensions. Adds an Extension column and
        removes deprecated codes.
        """
        codelists = self.standard_codelists()

        for name, rows in self.codelist_patches().items():
            if name.startswith(('+', '-')):
                basename = name[1:]

                if name.startswith('+'):
                    # Add the rows.
                    codelists[basename].extend(rows)
                    # Note that the rows may not all have the same columns, but DictWriter can handle this.
                else:
                    # Remove the codes. Multiple extensions can remove the same codes.
                    removed = [row['Code'] for row in rows]
                    codelists[basename] = [row for row in codelists[basename] if row['Code'] not in removed]
            else:
                # Replace the rows.
                codelists[name] = rows

        return codelists

    def standard_codelists(self):
        """
        Returns the rows of the codelists within the standard. Adds an Extension column and removes deprecated codes.
        """
        # Populate the file cache (though this method probably shouldn't have to know about `_file_cache`).
        self.get_standard_file_contents('release-schema.json')

        codelists = {}

        for path, content in self._file_cache.items():
            name = os.path.basename(path)
            if 'codelists' in path.split(os.sep) and name:
                codelists[name] = _append_extension(name, content, 'OCDS Core')

        return codelists

    def get_standard_file_contents(self, basename):
        """
        Returns the contents of the file within the standard.

        Downloads the given version of the standard, and caches the contents of files in the schema/ directory.
        """
        if not self._file_cache:
            url = 'https://codeload.github.com/open-contracting/standard/zip/' + self.standard_version
            response = requests.get(url)
            response.raise_for_status()
            zipfile = ZipFile(BytesIO(response.content))
            names = zipfile.namelist()
            path = 'standard/schema/'
            start = len(names[0] + path)
            for name in names[1:]:
                if path in name:
                    self._file_cache[name[start:]] = zipfile.read(name).decode('utf-8')

        return self._file_cache[basename]
