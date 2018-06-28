import csv
import gettext
import glob
import json
import logging.config
import os
from collections import OrderedDict

from ocdsdocumentationsupport import TRANSLATABLE_CODELIST_HEADERS, TRANSLATABLE_SCHEMA_KEYWORDS

logger = logging.getLogger('ocdsdocumentationsupport')


def translate_codelists(domain, sourcedir, builddir, localedir, language):
    """
    Writes files, translating each header and the Title, Description and Extension values of codelist CSV files.

    These files are typically referenced by `csv-table-no-translate` directives.

    Args:
        domain: The gettext domain.
        sourcedir: The path to the directory containing the codelist CSV files.
        builddir: The path to the build directory.
        localedir: The path to the `locale` directory.
        language: A two-letter lowercase ISO369-1 code or BCP47 language tag.
    """
    logger.info('Translating codelists to {} using "{}" domain, from {} to {}'.format(
        language, domain, sourcedir, builddir))

    os.makedirs(builddir, exist_ok=True)

    translator = gettext.translation(domain, localedir, languages=[language], fallback=language == 'en')

    for file in glob.glob(os.path.join(sourcedir, '*.csv')):
        with open(file) as r, open(os.path.join(builddir, os.path.basename(file)), 'w') as w:
            # This should roughly match the logic of the `codelists_extract` Babel extractor.
            reader = csv.DictReader(r)
            fieldnames = [translator.gettext(fieldname) for fieldname in reader.fieldnames]

            writer = csv.DictWriter(w, fieldnames, lineterminator='\n')
            writer.writeheader()

            for row in reader:
                new_row = {}
                for key, value in row.items():
                    value = value.strip()
                    if key in TRANSLATABLE_CODELIST_HEADERS and value:
                        value = translator.gettext(value)
                    new_row[translator.gettext(key)] = value
                writer.writerow(new_row)


def translate_schema(domain, filenames, sourcedir, builddir, localedir, language):
    """
    Writes files, translating the "title" and "description" values of JSON Schema files.

    These files are typically referenced by `jsonschema` directives.

    Args:
        domain: The gettext domain.
        filenames: A list of JSON Schema filenames to translate.
        sourcedir: The path to the directory containing the JSON Schema files.
        builddir: The path to the build directory.
        localedir: The path to the `locale` directory.
        language: A two-letter lowercase ISO369-1 code or BCP47 language tag.
    """
    logger.info('Translating schema to {} using "{}" domain, from {} to {}'.format(
        language, domain, sourcedir, builddir))

    for name in filenames:
        os.makedirs(os.path.dirname(os.path.join(builddir, name)), exist_ok=True)

    version = os.environ.get('TRAVIS_BRANCH', 'latest')

    # This should roughly match the logic of the `jsonschema_extract` Babel extractor.
    def translate_data(data):
        if isinstance(data, list):
            for item in data:
                translate_data(item)
        elif isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, str):
                    value = value.strip()
                    if key in TRANSLATABLE_SCHEMA_KEYWORDS and value:
                        data[key] = translator.gettext(value).replace('{{version}}', version).replace('{{lang}}', language)  # noqa: E501
                translate_data(value)

    translator = gettext.translation(domain, localedir, languages=[language], fallback=language == 'en')

    for name in filenames:
        with open(os.path.join(sourcedir, name)) as r, open(os.path.join(builddir, name), 'w') as w:
            data = json.load(r, object_pairs_hook=OrderedDict)
            translate_data(data)
            json.dump(data, w, indent=2, separators=(',', ': '), ensure_ascii=False)
