import csv
import json
import os
from collections import OrderedDict
from contextlib import contextmanager

from ocdsdocumentationsupport.profile_builder import ProfileBuilder

TRANSLATABLE_CODELIST_HEADERS = ('Title', 'Description', 'Extension')
TRANSLATABLE_SCHEMA_KEYWORDS = ('title', 'description')
VALID_FIELDNAMES = ('Code', 'Title', 'Description', 'Extension')


def build_profile(basedir, standard_version, extension_versions, registry_base_url=None):
    """
    Pulls extensions into a profile.

    - Writes extensions' README.md files (docs/extensions/{id}.md)
    - Merges extensions' JSON Merge Patch files for OCDS' release-schema.json (schema/profile/release-schema.json)
    - Writes extensions' codelist files (schema/profile/codelists)
    - Patches OCDS' release-schema.json with extensions' JSON Merge Patch files (schema/patched/release-schema.json)
    - Patches OCDS' codelist files with extensions' codelist files (schema/patched/codelists)

    The profile's codelists exclude deprecated codes and add an Extension column.

    `basedir` is the profile's schema/ directory.
    """
    @contextmanager
    def open_file(name, mode):
        """
        Creates the directory if it doesn't exist.
        """
        os.makedirs(os.path.dirname(name), exist_ok=True)

        f = open(name, mode)
        try:
            yield f
        finally:
            f.close()

    def write_json_file(data, *parts):
        with open_file(os.path.join(basedir, *parts), 'w') as f:
            json.dump(data, f, indent=2, separators=(',', ': '))
            f.write('\n')

    def write_codelist_file(codelist, fieldnames, *parts):
        with open_file(os.path.join(basedir, *parts, 'codelists', codelist.name), 'w') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator='\n', extrasaction='ignore')
            writer.writeheader()
            writer.writerows(codelist)

    builder = ProfileBuilder(standard_version, extension_versions, registry_base_url)
    extension_codelists = builder.extension_codelists()
    directories_and_schema = {
        'profile': builder.release_schema_patch(),
        'patched': builder.patched_release_schema(),
    }

    # Write the documentation files.
    for extension in builder.extensions():
        with open_file(os.path.join(basedir, '..', 'docs', 'extensions', '{}.md'.format(extension.id)), 'w') as f:
            f.write(extension.remote('README.md'))

    # Write the JSON Schema Patch and JSON Schema files.
    for directory, schema in directories_and_schema.items():
        write_json_file(schema, directory, 'release-schema.json')

    # Write the extensions' codelists.
    for codelist in extension_codelists:
        write_codelist_file(codelist, codelist.fieldnames, 'profile')

    # Write the patched codelists.
    for codelist in builder.patched_codelists():
        codelist.add_extension_column('Extension')
        codelist.remove_deprecated_codes()
        fieldnames = [fieldname for fieldname in codelist.fieldnames if fieldname in VALID_FIELDNAMES]
        write_codelist_file(codelist, fieldnames, 'patched')

    # Update the "codelists" field in extension.json.
    with open(os.path.join(basedir, 'profile', 'extension.json')) as f:
        metadata = json.load(f, object_pairs_hook=OrderedDict)

    codelists = [codelist.name for codelist in extension_codelists]

    if codelists:
        metadata['codelists'] = codelists
    else:
        metadata.pop('codelists', None)

    write_json_file(metadata, 'profile', 'extension.json')
