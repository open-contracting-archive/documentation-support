import os
from tempfile import TemporaryDirectory

from ocdsdocumentationsupport.babel_extractors import codelists_extract, jsonschema_extract

codelist = b"""Code,Title,Description,Extension,Category
  foo  ,  bar  ,  baz  ,  bzz  ,  zzz  
  bar  ,       ,  bzz  ,  zzz  ,  foo  
  baz  ,  bzz  ,       ,  foo  ,  bar  
  bzz  ,  zzz  ,  foo  ,       ,  baz  
"""

schema = b"""{
    "title": {
        "oneOf": [{
            "title": "  foo  ",
            "description": "  bar  "
        }, {
            "title": "  baz  ",
            "description": "  bzz  "
        }]
    },
    "description": {
        "title": "  zzz  "
    }
}"""

def assert_result(filename, content, method, expected):
    with TemporaryDirectory() as d:
        with open(os.path.join(d, filename), 'wb') as f:
            f.write(content)

        with open(os.path.join(d, filename), 'rb') as f:
            assert list(method(f, None, None, None)) == expected


def test_codelists_extract():
    assert_result('test.csv', codelist, codelists_extract, [
        (0, '', 'Code', ''),
        (0, '', 'Title', ''),
        (0, '', 'Description', ''),
        (0, '', 'Extension', ''),
        (0, '', 'Category', ''),
        (1, '', 'bar', ['Title']),
        (1, '', 'baz', ['Description']),
        (1, '', 'bzz', ['Extension']),
        (2, '', 'bzz', ['Description']),
        (2, '', 'zzz', ['Extension']),
        (3, '', 'bzz', ['Title']),
        (3, '', 'foo', ['Extension']),
        (4, '', 'zzz', ['Title']),
        (4, '', 'foo', ['Description']),
    ])


def test_codelists_extract_currency():
    assert_result('currency.csv', codelist, codelists_extract, [
        (0, '', 'Code', ''),
        (0, '', 'Title', ''),
        (0, '', 'Description', ''),
        (0, '', 'Extension', ''),
        (0, '', 'Category', ''),
    ])


def test_jsonschema_extract():
    assert_result('schema.json', schema, jsonschema_extract, [
        (1, '', 'foo', ['/title/oneOf/0/title']),
        (1, '', 'bar', ['/title/oneOf/0/description']),
        (1, '', 'baz', ['/title/oneOf/1/title']),
        (1, '', 'bzz', ['/title/oneOf/1/description']),
        (1, '', 'zzz', ['/description/title']),
    ])
