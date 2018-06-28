import json
import logging
from collections import OrderedDict

from ocdsdocumentationsupport.profile_builder import ProfileBuilder

standard_codelists = [
    'awardCriteria.csv',
    'awardStatus.csv',
    'contractStatus.csv',
    'currency.csv',
    'documentType.csv',
    'extendedProcurementCategory.csv',
    'initiationType.csv',
    'itemClassificationScheme.csv',
    'method.csv',
    'milestoneStatus.csv',
    'milestoneType.csv',
    'partyRole.csv',
    'procurementCategory.csv',
    'relatedProcess.csv',
    'relatedProcessScheme.csv',
    'releaseTag.csv',
    'submissionMethod.csv',
    'tenderStatus.csv',
    'unitClassificationScheme.csv',
]

new_extension_codelists = [
    # ppp
    'metricID.csv',
    'milestoneCode.csv',
    # charges, tariffs
    'chargePaidBy.csv',
]


def test_extensions():
    builder = ProfileBuilder('1__1__3', OrderedDict([('charges', 'master'), ('location', 'v1.1.3')]))
    result = list(builder.extensions())

    assert len(result) == 2
    assert result[0].as_dict() == {
        'id': 'charges',
        'date': '',
        'version': 'master',
        'base_url': 'https://raw.githubusercontent.com/open-contracting/ocds_charges_extension/master/',
        'download_url': 'https://github.com/open-contracting/ocds_charges_extension/archive/master.zip',
    }
    assert result[1].as_dict() == {
        'id': 'location',
        'date': '2018-02-01',
        'version': 'v1.1.3',
        'base_url': 'https://raw.githubusercontent.com/open-contracting/ocds_location_extension/v1.1.3/',
        'download_url': 'https://api.github.com/repos/open-contracting/ocds_location_extension/zipball/v1.1.3',
    }


def test_release_schema_patch():
    # Use the ppp extension to test null values.
    builder = ProfileBuilder('1__1__3', OrderedDict([('ppp', 'v1.1.3'), ('location', 'v1.1.3')]))
    result = builder.release_schema_patch()

    # Merges patches.
    assert 'Location' in result['definitions']

    # Preserves null values.
    assert result['properties']['buyer'] is None
    assert 'REPLACE_WITH_NULL' not in json.dumps(result)


def test_patched_release_schema():
    # Use the ppp extension to test null values.
    builder = ProfileBuilder('1__1__3', OrderedDict([('ppp', 'v1.1.3'), ('location', 'v1.1.3')]))
    result = builder.patched_release_schema()

    # Patches core.
    assert '$schema' in result
    assert 'Location' in result['definitions']

    # Removes null'ed fields.
    assert 'buyer' not in result['properties']


def test_extension_codelists(caplog):
    # Note: We can't yet test, using real data, whether an error is raised if a codelist replacement either doesn't
    # contain added codes, or contains removed codes. If we were to use test data, we could create a test registry
    # and test extensions, or mock HTTP requests…. For now, additions were tested manually. We also can't yet test
    # whether an error is raised if two codelist replacements differ.

    with caplog.at_level(logging.INFO):
        # charges and tariffs both have chargePaidBy.csv, but the content is identical, so should not error. ppp has
        # documentType.csv and tariffs has +documentType.csv, but documentType.csv contains the codes added by
        # +documentType.csv, so should not error. ppp and enquiries both have +partyRole.csv.
        builder = ProfileBuilder('1__1__3', OrderedDict([
            ('ppp', 'v1.1.3'),
            ('enquiries', 'v1.1.3'),
            ('charges', 'master'),
            ('tariffs', 'master'),
        ]))
        result = builder.extension_codelists()

        # Collects codelists.
        assert len(result) == 9
        assert list(result.keys()) == [
            '+milestoneType.csv',
            '+partyRole.csv',
            '-partyRole.csv',
            '+releaseTag.csv',
            'initiationType.csv',
            'documentType.csv',
        ] + new_extension_codelists

        # Preserves content.
        assert len(result['initiationType.csv']) == 1
        assert len(result['initiationType.csv'][0]) == 3
        assert result['initiationType.csv'][0]['Code'] == 'ppp'
        assert result['initiationType.csv'][0]['Title'] == 'Public Private Partnership'
        assert result['initiationType.csv'][0]['Description'].startswith('An open competitive bidding or tendering ')

        # Combines codelist additions and removals.
        assert len(result['+partyRole.csv']) == 16
        assert result['+partyRole.csv'][-1]['Code'] == 'enquirer'

        # Logs ignored codelists.
        assert len(caplog.records) == 1
        assert caplog.records[-1].levelname == 'INFO'
        assert caplog.records[-1].message == 'documentType.csv has the codes added by +documentType.csv - ignoring +documentType.csv'  # noqa


def test_patched_codelists(caplog):
    with caplog.at_level(logging.INFO):
        builder = ProfileBuilder('1__1__3', OrderedDict([
            ('ppp', 'v1.1.3'),
            ('charges', 'master'),
            ('tariffs', 'master'),
        ]))
        result = builder.patched_codelists()

        # Collects codelists.
        assert len(result) == 22
        assert list(result.keys()) == standard_codelists + new_extension_codelists

        # Preserves content.
        assert len(result['awardCriteria.csv']) == 8
        assert len(result['awardCriteria.csv'][0]) == 4
        assert result['awardCriteria.csv'][0]['Code'] == 'priceOnly'
        assert result['awardCriteria.csv'][0]['Title'] == 'Price Only'
        assert result['awardCriteria.csv'][0]['Description'].startswith('The award will be made to the qualified bid')
        assert result['awardCriteria.csv'][0]['Deprecated'] == ''

        # Adds codes.
        assert any(row['Code'] == 'publicAuthority' for row in result['partyRole.csv'])

        # Removes codes.
        assert not any(row['Code'] == 'buyer' for row in result['partyRole.csv'])

        # Replaces list.
        assert all(row['Code'] == 'ppp' for row in result['initiationType.csv'])

        # Logs ignored codelists.
        assert len(caplog.records) == 1
        assert caplog.records[-1].levelname == 'INFO'
        assert caplog.records[-1].message == 'documentType.csv has the codes added by +documentType.csv - ignoring +documentType.csv'  # noqa


def test_standard_codelists():
    builder = ProfileBuilder('1__1__3', OrderedDict())
    result = builder.standard_codelists()

    # Collects codelists.
    assert len(result) == 19
    assert list(result.keys()) == standard_codelists

    # Preserves content.
    assert len(result['awardCriteria.csv']) == 8
    assert len(result['awardCriteria.csv'][0]) == 4
    assert result['awardCriteria.csv'][0]['Code'] == 'priceOnly'
    assert result['awardCriteria.csv'][0]['Title'] == 'Price Only'
    assert result['awardCriteria.csv'][0]['Description'].startswith('The award will be made to the qualified bid with')
    assert result['awardCriteria.csv'][0]['Deprecated'] == ''


def test_get_standard_file_contents():
    builder = ProfileBuilder('1__1__3', OrderedDict())
    data = builder.get_standard_file_contents('release-schema.json')
    # Repeat requests should return the same result.
    data = builder.get_standard_file_contents('release-schema.json')

    assert json.loads(data)
