import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="acsys",
    version="0.8.3",
    author="Rich Neswold",
    author_email="neswold@fnal.gov",
    description="ACSys Client library",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://cdcvs.fnal.gov/redmine/projects/py/wiki/Acsys",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    install_requires=[
        'gssapi',
    ],
    python_requires='>=3.6',
)
