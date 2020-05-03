import setuptools
import versioneer


with open('README.rst') as f:
    readme = f.read()


extras_require_test = [
    'coverage',
    'mypy',
    'pytest',
    'pytest-cov',
    'tox',
]


setuptools.setup(
    name='ciborg',
    author='Kyle Altendorf',
    author_email='sda@fstab.net',
    description='Generate CI configuration for various services',
    long_description=readme,
    long_description_content_type='text/x-rst',
    url='https://github.com/altendky/ciborg',
    packages=setuptools.find_packages('src'),
    package_dir={'': 'src'},
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    license='MIT',
    classifiers=[
        # complete classifier list:
        #   https://pypi.org/pypi?%3Aaction=list_classifiers
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Operating System :: POSIX :: Linux',
        'Operating System :: MacOS',
        'Operating System :: Microsoft :: Windows',
    ],
    python_requires='>=3.6',
    entry_points={
        'console_scripts': [
            'ciborg = ciborg.cli:cli'
        ],
    },
    install_requires=[
        'attrs',
        'click',
        'importlib_resources',
        'marshmallow',
        'marshmallow_polyfield',
        'pyrsistent',
        'pyyaml',
    ],
    extras_require={
        'dev': [
            'gitignoreio',
        ] + extras_require_test,
        'test': extras_require_test,
    },
    include_package_data=True,
)
