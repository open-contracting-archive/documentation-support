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


def test_codelist_patches(caplog):
    # Note: We can't yet test, using real data, whether an error is raised if a codelist replacement either doesn't
    # contain added codes, or contains removed codes. If we were to use test data, we could create a test registry
    # and test extensions, or mock HTTP requests…. For now, additions were tested manually. We also can't yet test
    # whether an error is raised if two codelist replacements differ.

    with caplog.at_level(logging.INFO):
        # The charges and tariffs extensions have chargePaidBy.csv, but the content is identical, so should not error.
        # ppp has documentType.csv and tariffs has +documentType.csv, but documentType.csv contains the codes added by
        # +documentType.csv, so should not error. The ppp and enquiries extensions have +partyRole.csv.
        builder = ProfileBuilder('1__1__3', OrderedDict([
            ('ppp', 'v1.1.3'),
            ('enquiries', 'v1.1.3'),
            ('charges', 'master'),
            ('tariffs', 'master'),
        ]))
        result = builder.codelist_patches()

        assert len(result) == 9
        assert list(result.keys()) == [
            '+milestoneType.csv',
            '+partyRole.csv',
            '-partyRole.csv',
            '+releaseTag.csv',
            'initiationType.csv',
            'documentType.csv',
        ] + new_extension_codelists

        # Removes deprecated codes (there are none in extensions to test against, yet).

        # Sets Extension value and preserves other values.
        assert result['initiationType.csv'][-1]['Code'] == 'ppp'
        assert result['initiationType.csv'][-1]['Title'] == 'Public Private Partnership'
        assert result['initiationType.csv'][-1]['Description'].startswith('An open competitive bidding or tendering ')
        assert result['initiationType.csv'][-1]['Extension'] == 'OCDS for PPPs Extension'

        # Combines codelist additions and removals.
        assert len(result['+partyRole.csv']) == 16
        assert result['+partyRole.csv'][-1]['Code'] == 'enquirer'

        # Logs deprecated codes and ignored codelists.
        assert len(caplog.records) == 1
        assert caplog.records[-1].levelname == 'INFO'
        assert caplog.records[-1].message == 'documentType.csv has the codes added by +documentType.csv, ignoring +documentType.csv'  # noqa


def test_patched_codelists(caplog):
    with caplog.at_level(logging.INFO):
        builder = ProfileBuilder('1__1__3', OrderedDict([
            ('ppp', 'v1.1.3'),
            ('charges', 'master'),
            ('tariffs', 'master'),
        ]))
        result = builder.patched_codelists()

        assert len(result) == 22
        assert list(result.keys()) == standard_codelists + new_extension_codelists

        # Removes deprecated codes.
        assert len(result['awardCriteria.csv']) == 4

        # Sets Extension value and preserves other values.
        assert result['awardCriteria.csv'][-1]['Code'] == 'ratedCriteria'
        assert result['awardCriteria.csv'][-1]['Title'] == 'Rated Criteria'
        assert result['awardCriteria.csv'][-1]['Description'].startswith('The award will be made to the qualified bid')
        assert result['awardCriteria.csv'][-1]['Extension'] == 'OCDS Core'

        # Adds codes.
        assert any(row['Code'] == 'publicAuthority' for row in result['partyRole.csv'])

        # Removes codes.
        assert not any(row['Code'] == 'buyer' for row in result['partyRole.csv'])

        # Replaces list.
        assert all(row['Code'] == 'ppp' for row in result['initiationType.csv'])

        # Logs deprecated codes and ignored codelists.
        assert len(caplog.records) == 5
        for i, code in enumerate(('lowestCost', 'bestProposal', 'bestValueToGovernment', 'singleBidOnly')):
            assert caplog.records[i].levelname == 'INFO'
            assert caplog.records[i].message == '... skipping deprecated code {} in awardCriteria.csv'.format(code)
        assert caplog.records[-1].levelname == 'INFO'
        assert caplog.records[-1].message == 'documentType.csv has the codes added by +documentType.csv, ignoring +documentType.csv'  # noqa


def test_standard_codelists(caplog):
    with caplog.at_level(logging.INFO):
        builder = ProfileBuilder('1__1__3', OrderedDict())
        result = builder.standard_codelists()

        # Collects all codelists.
        assert len(result) == 19
        assert list(result.keys()) == standard_codelists

        # Removes Deprecated column.
        assert list(result['awardCriteria.csv'][0].keys()) == [
            'Code',
            'Title',
            'Description',
            'Extension',
        ]

        # Removes deprecated codes.
        assert len(result['awardCriteria.csv']) == 4

        # Sets Extension value and preserves other values.
        assert result['awardCriteria.csv'][-1]['Code'] == 'ratedCriteria'
        assert result['awardCriteria.csv'][-1]['Title'] == 'Rated Criteria'
        assert result['awardCriteria.csv'][-1]['Description'].startswith('The award will be made to the qualified bid')
        assert result['awardCriteria.csv'][-1]['Extension'] == 'OCDS Core'

        # Logs deprecated codes.
        assert len(caplog.records) == 4
        for i, code in enumerate(('lowestCost', 'bestProposal', 'bestValueToGovernment', 'singleBidOnly')):
            assert caplog.records[i].levelname == 'INFO'
            assert caplog.records[i].message == '... skipping deprecated code {} in awardCriteria.csv'.format(code)


def test_get_standard_file_contents():
    builder = ProfileBuilder('1__1__3', OrderedDict())
    data = builder.get_standard_file_contents('release-schema.json')
    # Repeat requests should return the same result.
    data = builder.get_standard_file_contents('release-schema.json')

    assert json.loads(data)
