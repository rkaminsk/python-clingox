from textwrap import dedent
from setuptools import setup

setup(
    version='1.0.1',
    name='clingox',
    description='Support library for clingo.',
    long_description=dedent('''\
        Please check the [API documentation](https://potassco.org/clingo/python-api/current/) on how to use this module.
        '''),
    long_description_content_type='text/markdown',
    author='Roland Kaminski',
    author_email='kaminski@cs.uni-potsdam.de',
    license='MIT',
    url='https://github.com/potassco/python-clingox',
    install_requires=['clingo'],
    packages=['clingox'],
    package_data={'clingox': ['py.typed']},
    zip_safe=False,
    python_requires=">=3.6"
)
