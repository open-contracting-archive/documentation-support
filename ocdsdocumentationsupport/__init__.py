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
    def write_csv_file(basedir, codelist, fieldnames):
        builddir = os.path.join(basedir, 'codelists')

        if not os.path.exists(builddir):
            os.makedirs(builddir)

        with open(os.path.join(builddir, codelist.name), 'w') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator='\n', extrasaction='ignore')
            writer.writeheader()
            writer.writerows(codelist)

    builder = ProfileBuilder(standard_version, extension_versions, registry_base_url)
    extension_codelists = builder.extension_codelists()

    directories_and_schema = {
        'profile': builder.release_schema_patch(),
        'patched': builder.patched_release_schema(),
    }

    for extension in builder.extensions():
        with open(os.path.join(basedir, '..', 'docs', 'extensions', '{}.md'.format(extension.id)), 'w') as f:
            f.write(extension.remote('README.md'))

    for directory, schema in directories_and_schema.items():
        with open(os.path.join(basedir, directory, 'release-schema.json'), 'w') as f:
            json.dump(schema, f, indent=2, separators=(',', ': '))
            f.write('\n')

    for codelist in extension_codelists:
        write_csv_file(os.path.join(basedir, 'profile'), codelist, codelist.fieldnames)

    for codelist in builder.patched_codelists():
        codelist.add_extension_column('Extension')
        codelist.remove_deprecated_codes()
        fieldnames = [fieldname for fieldname in codelist.fieldnames if fieldname in VALID_FIELDNAMES]

        write_csv_file(os.path.join(basedir, 'patched'), codelist, fieldnames)

    with open(os.path.join(basedir, 'profile', 'extension.json')) as f:
        metadata = json.load(f, object_pairs_hook=OrderedDict)

    metadata['codelists'] = [codelist.name for codelist in extension_codelists]

    with open(os.path.join(basedir, 'profile', 'extension.json'), 'w') as f:
        json.dump(metadata, f, indent=2, separators=(',', ': '))
        f.write('\n')
