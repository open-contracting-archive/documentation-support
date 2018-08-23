import csv
import gettext
import json
import os
from tempfile import TemporaryDirectory

from ocdsdocumentationsupport.translation import translate_codelists, translate_schema

codelist = """Code,Title,Description
open,  Open  ,  All interested suppliers may submit a tender.  
selective,  Selective  ,  Only qualified suppliers are invited to submit a tender.  
"""  # noqa

schema = """{
  "title": "Schema for an Open Contracting Record package {{version}}",
  "description": "The record package contains a list of records along with some publishing…",
  "definitions": {
    "record": {
      "properties": {
        "releases": {
          "title": "Releases",
          "description": "An array of linking identifiers or releases",
          "oneOf": [
            {
              "title": "  Linked releases  ",
              "description": "  A list of objects that identify the releases associated with this Open…  "
            },
            {
              "title": "  Embedded releases  ",
              "description": "  A list of releases, with all the data. The releases MUST be sorted into date…  "
            }
          ]
        }
      }
    }
  }
}"""


def test_translate_codelists(monkeypatch, caplog):
    class Translation(object):
        def __init__(self, *args, **kwargs):
            pass

        def gettext(self, *args, **kwargs):
            return {
                'Code': 'Código',
                'Title': 'Título',
                'Description': 'Descripción',
                'Open': 'Abierta',
                'Selective': 'Selectiva',
                'All interested suppliers may submit a tender.': 'Todos los proveedores interesados pueden enviar una propuesta.',  # noqa
                'Only qualified suppliers are invited to submit a tender.': 'Sólo los proveedores calificados son invitados a enviar una propuesta.',  # noqa
            }[args[0]]

    monkeypatch.setattr(gettext, 'translation', Translation)

    with TemporaryDirectory() as sourcedir:
        with open(os.path.join(sourcedir, 'method.csv'), 'w') as f:
            f.write(codelist)

        with TemporaryDirectory() as builddir:
            translate_codelists('codelists', sourcedir, builddir, '', 'es')

            with open(os.path.join(builddir, 'method.csv')) as f:
                rows = [dict(row) for row in csv.DictReader(f)]

            assert rows == [{
                'Código': 'open',
                'Descripción': 'Todos los proveedores interesados pueden enviar una propuesta.',
                'Título': 'Abierta'
            }, {
                'Código': 'selective',
                'Descripción': 'Sólo los proveedores calificados son invitados a enviar una propuesta.',
                'Título': 'Selectiva'
            }]

    assert len(caplog.records) == 1
    assert caplog.records[0].levelname == 'INFO'
    assert caplog.records[0].message == 'Translating codelists to es using "codelists" domain, ' \
                                        'from {} to {}'.format(sourcedir, builddir)


def test_translate_schema(monkeypatch, caplog):
    class Translation(object):
        def __init__(self, *args, **kwargs):
            pass

        def gettext(self, *args, **kwargs):
            return {
                'Schema for an Open Contracting Record package {{version}}': 'Esquema para un paquete de Registros de Contrataciones Abiertas {{version}}',  # noqa
                'The record package contains a list of records along with some publishing…':  'El paquete de registros contiene una lista de registros junto con algunos…',  # noqa
                'Releases': 'Entregas',
                'An array of linking identifiers or releases': 'Una matriz de enlaces a identificadores o entregas',
                'Linked releases': 'Entregas vinculadas',
                'A list of objects that identify the releases associated with this Open…':  'Una lista de objetos que identifican las entregas asociadas con este Open…',  # noqa
                'Embedded releases': 'Entregas embebidas',
                'A list of releases, with all the data. The releases MUST be sorted into date…':  'Una lista de entregas, con todos los datos. Las entregas DEBEN ordenarse…',  # noqa
            }[args[0]]

    monkeypatch.setattr(gettext, 'translation', Translation)

    with TemporaryDirectory() as sourcedir:
        with open(os.path.join(sourcedir, 'record-package-schema.json'), 'w') as f:
            f.write(schema)

        with open(os.path.join(sourcedir, 'untranslated.json'), 'w') as f:
            f.write(schema)

        with TemporaryDirectory() as builddir:
            translate_schema('schema', ['record-package-schema.json'], sourcedir, builddir, '', 'es', '1.1')

            with open(os.path.join(builddir, 'record-package-schema.json')) as f:
                data = json.load(f)

            assert not os.path.exists(os.path.join(builddir, 'untranslated.json'))

            assert data == {
              "title": "Esquema para un paquete de Registros de Contrataciones Abiertas 1.1",
              "description": "El paquete de registros contiene una lista de registros junto con algunos…",
              "definitions": {
                "record": {
                  "properties": {
                    "releases": {
                      "title": "Entregas",
                      "description": "Una matriz de enlaces a identificadores o entregas",
                      "oneOf": [
                        {
                          "title": "Entregas vinculadas",
                          "description": "Una lista de objetos que identifican las entregas asociadas con este Open…"
                        },
                        {
                          "title": "Entregas embebidas",
                          "description": "Una lista de entregas, con todos los datos. Las entregas DEBEN ordenarse…"
                        }
                      ]
                    }
                  }
                }
              }
            }

    assert len(caplog.records) == 1
    assert caplog.records[0].levelname == 'INFO'
    assert caplog.records[0].message == 'Translating schema to es using "schema" domain, ' \
                                        'from {} to {}'.format(sourcedir, builddir)
