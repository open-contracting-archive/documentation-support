from setuptools import setup, find_packages

setup(  # noqa: E131
    name='ocds-documentation-support',
    version='0.0.0',
    author='James McKinney',
    author_email='james@slashpoundbang.com',
    url='https://github.com/open-contracting/documentation-support',
    platforms=['any'],
    license='Apache',
    packages=find_packages(),
    entry_points='''
[babel.extractors]
codelists_text = ocds_documentation_support:codelists_extract
jsonschema_text = ocds_documentation_support:jsonschema_extract
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
        'sphinxcontrib-jsonschema==0.9.4',  # see below
          'jsonpointer==1.10',
          'jsonref==0.1',
          'recommonmark==0.4.0',  # see below
            'CommonMark==0.7.3',
        'ocds_sphinx_directives==0.0.0',  # see below
        'sphinxcontrib-opendataservices==0.0.0',  # see below
        'standard_theme==0.0.0',  # see below

        # Tests

        'flake8==3.3.0',
          'mccabe==0.6.1',
          'pycodestyle==2.3.1',
          'pyflakes==1.5.0',

        # Utils

        'transifex-client',
    ],
    dependency_links=[
      'git+https://github.com/open-contracting/standard_theme.git@open_contracting#egg=standard_theme-0.0.0',
      'git+https://github.com/open-contracting/ocds_sphinx_directives.git@41cb588bc2e1e7c929e3afbb8253dd7f87758831#egg=ocds_sphinx_directives-0.0.0',  # noqa: E501
      'git+https://github.com/jpmckinney/sphinxcontrib-jsonschema.git@9c26c6da2b4091f0306c1bd2e5e4baed891157b1#egg=sphinxcontrib-jsonschema-0.9.4',  # noqa: E501
      'git+https://github.com/OpenDataServices/sphinxcontrib-opendataservices.git@fab0ff0167d32ec243d42f272e0e50766299c078#egg=sphinxcontrib-opendataservices-0.0.0',  # noqa: E501
      'git+https://github.com/rtfd/recommonmark.git@81d7c6f7b37981ac22571dd91a7cc9d24c3e66a1#egg=recommonmark-0.4.0',
    ]
)
