import csv
import json
import os
from collections import OrderedDict

from ocdsdocumentationsupport.profile_builder import ProfileBuilder

TRANSLATABLE_CODELIST_HEADERS = ('Title', 'Description', 'Extension')
TRANSLATABLE_SCHEMA_KEYWORDS = ('title', 'description')
VALID_FIELDNAMES = ('Code', 'Title', 'Description', 'Extension')


def build_profile(basedir, standard_version, extension_versions, registry_base_url=None):
    """
    Pulls extensions into a profile.

    - Writes extensions' README.md files (docs/extensions/{id}.md)
    - Merges extensions' JSON Schema Patch files for OCDS' release-schema.json (schema/profile/release-schema.json)
    - Writes extensions' codelist files (schema/profile/codelists)
    - Patches OCDS' release-schema.json with extensions' JSON Schema Patch files (schema/patched/release-schema.json)
    - Patches OCDS' codelist files with extensions' codelist files (schema/patched/codelists)

    The profile's codelists exclude deprecated codes and add an Extension column.

    `basedir` is the profile's schema/ directory.
    """
    builder = ProfileBuilder(standard_version, extension_versions, registry_base_url)

    directories_and_schema = {
        'profile': builder.release_schema_patch(),
        'patched': builder.patched_release_schema(),
    }

    directories_and_codelists = {
        'profile': {
            'codelists': builder.extension_codelists(),
            'normalize': False,
        },
        'patched': {
            'codelists': builder.patched_codelists(),
            'normalize': True,
        }
    }

    for extension in builder.extensions():
        with open(os.path.join(basedir, '..', 'docs', 'extensions', '{}.md'.format(extension.id)), 'w') as f:
            f.write(extension.remote('README.md'))

    for directory, schema in directories_and_schema.items():
        with open(os.path.join(basedir, directory, 'release-schema.json'), 'w') as f:
            json.dump(schema, f, indent=2, separators=(',', ': '))
            f.write('\n')

    for directory, configuration in directories_and_codelists.items():
        for codelist in configuration['codelists']:
            if configuration['normalize']:
                codelist.add_extension_column('Extension')
                codelist.remove_deprecated_codes()

            # Calculate the fieldnames that can be included.
            fieldnames = OrderedDict()
            for row in codelist:
                for field in row:
                    fieldnames[field] = True

            if configuration['normalize']:
                fieldnames = [fieldname for fieldname in fieldnames if fieldname in VALID_FIELDNAMES]
            else:
                fieldnames = fieldnames.keys()

            with open(os.path.join(basedir, directory, 'codelists', codelist.name), 'w') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator='\n', extrasaction='ignore')
                writer.writeheader()
                writer.writerows(codelist)
