import csv
import gettext
import glob
import json
import os
import re
import shutil
from collections import OrderedDict
from io import BytesIO, StringIO
from zipfile import ZipFile

import json_merge_patch
import requests
from ocdsextensionregistry import ExtensionRegistry

TRANSLATABLE_CODELIST_HEADERS = ('Title', 'Description', 'Extension')
TRANSLATABLE_SCHEMA_KEYWORDS = ('title', 'description')


def apply_extensions(basedir, profile_identifier, extension_versions):
    """
    Pulls extensions into a profile. First, it:

    - Writes the base codelists from schema/base-codelists to compiledCodelists, skipping deprecated codes, adding an
      Extension column and removing any columns other than Code, Title, Description, Extension

    Then, for each extension and the profile itself, it:

    - Writes its README.md to docs/extensions/{id}.md
    - Merges its release-schema.json with the base schema and an empty extension
    - Writes its codelists to docs/extensions/codelists and schema/consolidatedExtension/codelists and then,
    for each codelist:
      - If it is a new codelist, writes it to compiledCodelists, with the same changes as above
      - If it modifies a base codelist in compiledCodelists, adds any new rows with the same changes as above

    Lastly, it writes the merged schema to schema/{id}-release-schema.json and merged extension to
    schema/consolidatedExtension/release-schema.json
    """
    def relative_path(*components):
        """
        Returns a path relative to this file.
        """
        return os.path.join(basedir, *components)

    def replace_nulls(content):
        """
        Replaces `null` with sentinel values, to preserve the null'ing of fields by extensions in the final patch.
        """
        return json.loads(re.sub(r':\s*null\b', ': "REPLACE_WITH_NULL"', content))

    def pluck_fieldnames(fieldnames, basename):
        """
        Normalizes the fieldnames in `compiledCodelists` to only include Code, Title, Description, Extension.
        """
        # Special case.
        if basename == 'documentType.csv':
            return fieldnames

        valid_fieldnames = ['Code', 'Title', 'Description', 'Extension']

        return [fieldname for fieldname in fieldnames if fieldname in valid_fieldnames]

    def write_csv_file(path, fieldnames, rows):
        """
        Writes a CSV file.
        """
        with open(path, 'w') as f:
            # Since `pluck_fieldnames` reduces the number of fields, we ignore any extra fields.
            writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator='\n', extrasaction='ignore')
            writer.writeheader()
            writer.writerows(rows)

    def process_codelist(basename, content, extension_name):
        """
        Modifies a base codelist by adding or removing codes if the codelist name in the extension starts with a plus
        or minus. Otherwise, copies the codelist and adds an Extension column.
        """
        if basename[0] in ('+', '-'):
            path = relative_path(compiled_codelists, basename[1:])
            if not os.path.isfile(path):
                raise Exception('Base codelist for {} is missing'.format(basename))

            rows = []
            with open(path, 'r') as f, StringIO(content.decode()) as g:
                reader = csv.DictReader(f)

                if basename.startswith('+'):
                    added = csv.DictReader(g)
                    # Left side `pluck_fieldnames` is needed for `+documentType.csv` from tariffs extension.
                    reader_fieldnames = pluck_fieldnames(reader.fieldnames, basename)
                    # Right side `pluck_fieldnames` is needed for `+partyRole.csv` from this profile.
                    if reader_fieldnames != pluck_fieldnames(added.fieldnames, basename) + ['Extension']:
                        raise Exception('Codelist {} from {} has different fields than the base codelist'.format(
                            basename, extension_name))
                    rows.extend(reader)
                    rows.extend(add_extension_to_rows(added, extension_name, basename))

                elif basename.startswith('-'):
                    removed = [row['Code'] for row in csv.DictReader(g)]
                    for row in reader:
                        if row['Code'] in removed:
                            continue
                        else:
                            rows.append(row)

            write_csv_file(path, reader.fieldnames, rows)
        else:
            path = relative_path(compiled_codelists, basename)
            with open(path, 'wb') as f:
                f.write(content)

            append_extension(path, extension_name, basename)

    def add_extension_to_rows(reader, extension_name, basename):
        """
        Returns a list of rows, adding an Extension column.
        """
        rows = []
        for row in reader:
            if row.get('Deprecated'):
                print('... skipping deprecated code {} in {}'.format(row['Code'], basename))
            else:
                row['Extension'] = extension_name
                rows.append(row)
        return rows

    def append_extension(path, extension_name, basename):
        """
        Rewrites a codelist CSV file, adding an Extension column.
        """
        with open(path) as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames + ['Extension']
            rows = add_extension_to_rows(reader, extension_name, basename)

        write_csv_file(path, pluck_fieldnames(fieldnames, basename), rows)

    # This method compiles codelists into `compiledCodelists`. FYI, the other codelist directories are:
    #
    # * `codelists`: The profile's original codelists
    # * `schema/base-codelists`: The standard's original codelists
    # * `docs/extensions/codelists`: The extensions' original codelists, downloaded by this script
    compiled_codelists = os.path.join('..', 'compiledCodelists')

    # The base schema will be progressively merged with extensions' schema and this profile's schema.
    with open(relative_path('base-release-schema.json')) as f:
        schema = json.load(f, object_pairs_hook=OrderedDict)

    # This profile's extension will be progressively merged, as well.
    profile_extension = {}

    # Codelists with the same name should be identical across extensions.
    codelists_seen = {}

    # Copy the base codelists to the compiled codelists, and add an Extension column.
    for filename in glob.glob(relative_path('base-codelists', '*.csv')):
        basename = os.path.basename(filename)
        path = relative_path(compiled_codelists, basename)
        shutil.copy(filename, path)
        append_extension(path, 'OCDS Core', basename)

    # Process extensions in this profile.
    url = 'https://raw.githubusercontent.com/open-contracting/extension_registry/master/extension_versions.csv'
    registry = ExtensionRegistry(url)
    for extension in registry:
        # Skip this profile, as we process it locally.
        if extension.id == profile_identifier:
            continue

        if extension.id not in extension_versions or extension.version != extension_versions[extension.id]:
            print('... skipping {} {}'.format(extension.id, extension.version))
            continue

        # The extension is part of the profile:
        print('Merging {}'.format(extension.id))

        # Merge the patch.
        response = requests.get(extension.base_url + 'release-schema.json')
        json_merge_patch.merge(schema, response.json())
        json_merge_patch.merge(profile_extension, replace_nulls(response.text))

        # Write the readme.
        readme = requests.get(extension.base_url + 'README.md').text
        with open(relative_path('..', 'docs', 'extensions', '{}.md'.format(extension.id)), 'w') as f:
            f.write(readme)

        # Process the codelists.
        response = requests.get(extension.download_url, allow_redirects=True, stream=True)
        if response.ok:
            zipfile = ZipFile(BytesIO(response.content))
            for f in zipfile.filelist:
                filename = f.filename
                if 'codelist' in filename and os.path.splitext(filename)[1] == '.csv':
                    basename = os.path.basename(filename)
                    content = zipfile.read(filename)

                    if basename in codelists_seen and codelists_seen[basename] != content:
                        raise Exception('codelist {} is different across extensions'.format(basename))
                    codelists_seen[basename] = content

                    # special case since the documentType.csv in PPP profile is already compiled
                    if basename != "+documentType.csv" and basename != "-documentType.csv":
                        with open(relative_path('..', 'docs', 'extensions', 'codelists', basename), 'wb') as f:
                            f.write(content)

                        with open(relative_path('..', 'schema',
                                                'consolidatedExtension', 'codelists', basename), 'wb') as f:
                            f.write(content)

                    print('    Processing {}'.format(basename))
                    process_codelist(basename, content, extension.metadata['name']['en'])
        else:
            print('ERROR: Could not find release ZIP for {}'.format(extension.id))

    # Process this profile.
    print('Merging {}'.format(profile_identifier))
    with open(relative_path('..', 'release-schema.json')) as f:
        content = f.read()
        json_merge_patch.merge(schema, json.loads(content, object_pairs_hook=OrderedDict))
        json_merge_patch.merge(profile_extension, replace_nulls(content))

    with open(relative_path('..', 'README.md')) as f:
        with open(relative_path('..', 'docs', 'extensions', '{}.md'.format(profile_identifier)), 'w') as g:
            g.write(f.read())

    for filename in glob.glob(relative_path('..', 'codelists', '*.csv')):
        with open(filename, 'rb') as f:
            basename = os.path.basename(filename)
            content = f.read()

            if basename in codelists_seen and codelists_seen[basename] != content:
                raise Exception('codelist {} is different across extensions'.format(basename))
            codelists_seen[basename] = content
            with open(relative_path('..', 'docs', 'extensions', 'codelists', basename), 'wb') as f:
                f.write(content)

            with open(relative_path('..', 'schema', 'consolidatedExtension', 'codelists', basename), 'wb') as f:
                f.write(content)

            print('Processing {}'.format(basename))
            process_codelist(basename, content, 'Public Private Partnership')

    # Write the two files.
    with open(relative_path('{}-release-schema.json'.format(profile_identifier)), 'w') as f:
        json.dump(schema, f, indent=2, separators=(',', ': '))
        f.write('\n')

    with open(relative_path('..', 'schema', 'consolidatedExtension', 'release-schema.json'), 'w') as f:
        f.write(json.dumps(profile_extension, indent=2, separators=(',', ': ')).replace('"REPLACE_WITH_NULL"', 'null'))
        f.write('\n')
