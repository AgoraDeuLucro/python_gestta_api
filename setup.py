from setuptools import setup

with open("README.md", "r") as arq:
    readme = arq.read()

setup(name='py_gestta',
    version='0.0.5',
    license='MIT License',
    author='Yuri Gomes',
    long_description=readme,
    long_description_content_type="text/markdown",
    author_email='yurialdegomes@gmail.com',
    keywords='gestta',
    description=u'Wrapper não oficial do Gestta',
    packages=['py_gestta'],
    install_requires=['requests'],)