from setuptools import setup, find_packages

setup(  # noqa: E131
    name='ocdsdocumentationsupport',
    version='0.0.0',
    packages=find_packages(),
    entry_points='''
[babel.extractors]
codelists_text = ocds_documentation_support.babel_extractors:codelists_extract
jsonschema_text = ocds_documentation_support.babel_extractors:jsonschema_extract
''',
    # The dependency trees are determined by `pipdeptree -fl`
    install_requires=[
        # Build

        # It should be safe to track the versions in:
        # https://github.com/OpenDataServices/sphinx-base/blob/master/requirements.txt
        'sphinx-intl==0.9.9',
          'Babel==2.4.0',
            'pytz==2017.2',
          'click==6.7',
          'setuptools==38.4.0',
          'six==1.10.0',
          'Sphinx==1.5.1',  # 1.5.2 breaks the translation of the sidebar menu
            'alabaster==0.7.10',
            'docutils==0.13.1',
            'imagesize==0.7.1',
            'Jinja2==2.9.6',
              'MarkupSafe==1.0',
            'Pygments==2.2.0',
            'requests==2.18.1',
            'snowballstemmer==1.2.1',
        # 'sphinxcontrib-jsonschema==0.9.3',  # use forked version
          'jsonpointer==1.10',
          'jsonref==0.1',
          # 'recommonmark==0.4.0',  # use unreleased version
            'CommonMark<0.6',

        # Tests

        'flake8==3.3.0',
          'mccabe==0.6.1',
          'pycodestyle==2.3.1',
          'pyflakes==1.5.0',

        # Utils

        'ocdsextensionregistry>=0.0.4',
        'json-merge-patch',
        'transifex-client',
    ],
    extras_require={
        'test': [
            'coveralls',
            'pytest',
            'pytest-cov',
        ],
    },
)
