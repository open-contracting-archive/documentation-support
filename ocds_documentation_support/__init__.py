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


def codelists_extract(fileobj, keywords, comment_tags, options):
    """
    Yields each header, and the Title, Description and Extension values of a codelist CSV file.

    Babel extractor used in setup.py
    """
    reader = csv.DictReader(StringIO(fileobj.read().decode()))
    for header in reader.fieldnames:
        yield 0, '', header.strip(), ''

    if os.path.basename(fileobj.name) != 'currency.csv':
        for row_number, row in enumerate(reader, 1):
            for key, value in row.items():
                if key in ('Title', 'Description', 'Extension') and value:
                    yield row_number, '', value.strip(), [key]


def jsonschema_extract(fileobj, keywords, comment_tags, options):
    """
    Yields the "title" and "description" values of a JSON Schema file.

    Babel extractor used in setup.py
    """
    def gather_text(data, pointer=''):
        if isinstance(data, list):
            for index, item in enumerate(data):
                yield from gather_text(item, pointer='{}/{}'.format(pointer, index))
        elif isinstance(data, dict):
            for key, value in data.items():
                if key in ('title', 'description') and isinstance(value, str):
                    yield value, '{}/{}'.format(pointer, key)
                yield from gather_text(value, pointer='{}/{}'.format(pointer, key))

    data = json.loads(fileobj.read().decode())
    for text, pointer in gather_text(data):
        yield 1, '', text.strip(), [pointer]


def translate_codelists(domain, sourcedir, builddir, localedir, language):
    """
    Writes files, translating each header and the `Title`, `Description` and `Extension` values of codelist CSV files.

    These files are typically referenced by `csv-table-no-translate` directives.

    Args:
        domain: The gettext domain.
        sourcedir: The path to the directory containing the codelist CSV files.
        builddir: The path to the build directory.
        localedir: The path to the `locale` directory.
        language: A two-letter lowercase ISO369-1 code or BCP47 language tag.
    """
    print('Translating codelists in {} to language {}'.format(sourcedir, language))

    translator = gettext.translation(domain, localedir, languages=[language], fallback=language == 'en')

    if not os.path.exists(builddir):
        os.makedirs(builddir)

    for file in glob.glob(os.path.join(sourcedir, '*.csv')):
        with open(file) as r, open(os.path.join(builddir, os.path.basename(file)), 'w') as w:
            reader = csv.DictReader(r)
            fieldnames = [translator.gettext(fieldname) for fieldname in reader.fieldnames]

            writer = csv.DictWriter(w, fieldnames, lineterminator='\n')
            writer.writeheader()

            for row in reader:
                new_row = {}
                for key, value in row.items():
                    if key in ('Title', 'Description', 'Extension') and value:
                        value = translator.gettext(value)
                    new_row[translator.gettext(key)] = value
                writer.writerow(new_row)


def translate_schema(domain, filenames, sourcedir, builddir, localedir, language):
    """
    Writes files, translating the `title` and `description` values of JSON Schema files.

    These files are typically referenced by `jsonschema` directives.

    Args:
        domain: The gettext domain.
        filenames: A list of JSON Schema filenames to translate.
        sourcedir: The path to the directory containing the JSON Schema files.
        builddir: The path to the build directory.
        localedir: The path to the `locale` directory.
        language: A two-letter lowercase ISO369-1 code or BCP47 language tag.
    """
    print('Translating schema in {} to language {}'.format(sourcedir, language))

    version = os.environ.get('TRAVIS_BRANCH', 'latest')

    def translate_data(data):
        if isinstance(data, list):
            for item in data:
                translate_data(item)
        elif isinstance(data, dict):
            for key, value in data.items():
                if key in ('title', 'description') and isinstance(value, str):
                    data[key] = translator.gettext(value).replace('{{version}}', version).replace('{{lang}}', language)
                translate_data(value)

    translator = gettext.translation(domain, localedir, languages=[language], fallback=language == 'en')

    if not os.path.exists(builddir):
        os.makedirs(builddir)

    for name in filenames:
        with open(os.path.join(sourcedir, name)) as r, open(os.path.join(builddir, name), 'w') as w:
            data = json.load(r, object_pairs_hook=OrderedDict)
            translate_data(data)
            json.dump(data, w, indent=2, separators=(',', ': '), ensure_ascii=False)


def apply_extensions(basedir, profile_extension_id, profile_extensions):
    """
    Pulls extensions into a profile. First, it:

    - Writes the base codelists from schema/base-codelists to compiledCodelists, skipping deprecated codes, adding an
      Extension column and removing any columns other than Code, Title, Description, Extension

    Then, for each extension and the profile itself, it:

    - Writes its README.md to docs/extensions/{id}.md
    - Merges its release-schema.json with the base schema and an empty extension
    - Writes its codelists to docs/extensions/codelists and then, for each codelist:
      - If it is a new codelist, writes it to compiledCodelists, with the same changes as above
      - If it modifies a base codelist in compiledCodelists, adds any new rows with the same changes as above

    Lastly, it writes the merged schema to schema/{id}-release-schema.json and merged extension to
    schema/{id}-extension.json
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
    reader = csv.DictReader(StringIO(requests.get(url).text))
    for row in reader:
        # Skip this profile, as we process it locally.
        if row['Id'] == profile_extension_id:
            continue

        # If the extension is part of the profile, merge the patch and write the readme.
        if row['Id'] in profile_extensions and row['Version'] == profile_extensions[row['Id']]:
            print('Merging {}'.format(row['Id']))
            response = requests.get(row['Base URL'] + 'release-schema.json')
            readme = requests.get(row['Base URL'] + 'README.md').text
            json_merge_patch.merge(schema, response.json())
            json_merge_patch.merge(profile_extension, replace_nulls(response.text))
            with open(relative_path('..', 'docs', 'extensions', '{}.md'.format(row['Id'])), 'w') as f:
                f.write(readme)
        else:
            print('... skipping {}'.format(row['Id']))
            continue

        parts = row['Base URL'].rsplit('/', 3)
        response = requests.get(row['Download URL'], allow_redirects=True, stream=True)
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
                    with open(relative_path('..', 'docs', 'extensions', 'codelists', basename), 'wb') as f:
                        f.write(content)

                    print('    Processing {}'.format(basename))
                    process_codelist(basename, content, extension['name']['en'])
        else:
            print('ERROR: Could not find release ZIP for {}'.format(row['Id']))

    # Process this profile.
    print('Merging {}'.format(profile_extension_id))
    with open(relative_path('..', 'release-schema.json')) as f:
        content = f.read()
        json_merge_patch.merge(schema, json.loads(content, object_pairs_hook=OrderedDict))
        json_merge_patch.merge(profile_extension, replace_nulls(content))

    with open(relative_path('..', 'README.md')) as f:
        with open(relative_path('..', 'docs', 'extensions', '{}.md'.format(profile_extension_id)), 'w') as g:
            g.write(f.read())

    for filename in glob.glob(relative_path('..', 'codelists', '*.csv')):
        with open(filename, 'rb') as f:
            basename = os.path.basename(filename)
            content = f.read()

            print('Processing {}'.format(basename))
            process_codelist(basename, content, 'Public Private Partnership')

    # Write the two files.
    with open(relative_path('{}-release-schema.json'.format(profile_extension_id)), 'w') as f:
        json.dump(schema, f, indent=2, separators=(',', ': '))
        f.write('\n')

    with open(relative_path('{}-extension.json'.format(profile_extension_id)), 'w') as f:
        f.write(json.dumps(profile_extension, indent=2, separators=(',', ': ')).replace('"REPLACE_WITH_NULL"', 'null'))
        f.write('\n')
