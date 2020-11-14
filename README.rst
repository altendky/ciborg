ciborg
======

Assimilate your CI services

|PyPI| |Pythons| |Azure| |codecov| |GitHub|

ciborg aims to provide two layers of control allowing you to write CI configuration that
is agnostic to the actual CI provider you use.  The first layer provides a CLI to
convert the ciborg configuration to CI provider specific configuration files.  This
layer is opinionated about proper CI practices and should be easily usable by all
developers to setup a quality CI pipeline.  The second layer provides a Python API
allowing more advanced users to build their own top level implementation using the basic
building blocks provided by ciborg.

Note:
    This project is in the early stages of development.  It has bootstrapped itself on
    `Azure Pipelines`_ and `GitHub Actions`_.

.. _Azure Pipelines: https://azure.microsoft.com/en-us/services/devops/pipelines/
.. _GitHub Actions: https://github.com/features/actions

.. |PyPI| image:: https://img.shields.io/pypi/v/ciborg.svg
   :alt: PyPI version
   :target: https://pypi.org/project/ciborg/

.. |Pythons| image:: https://img.shields.io/pypi/pyversions/ciborg.svg
   :alt: supported Python versions
   :target: https://pypi.org/project/ciborg/

.. |Azure| image:: https://dev.azure.com/altendky/ciborg/_apis/build/status/altendky.ciborg?branchName=develop
   :alt: Azure build status
   :target: https://dev.azure.com/altendky/ciborg/_build

.. |codecov| image:: https://codecov.io/gh/altendky/ciborg/branch/develop/graph/badge.svg
   :alt: codecov coverage status
   :target: https://codecov.io/gh/altendky/ciborg

.. |GitHub| image:: https://img.shields.io/github/last-commit/altendky/ciborg/develop.svg
   :alt: source on GitHub
   :target: https://github.com/altendky/ciborg
