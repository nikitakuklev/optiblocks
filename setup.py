import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    LONG_DESCRIPTION = fh.read()

INSTALL_REQUIRES = [
    'numpy>=1.13.3',
    'pandas>=1.0',
    'pyqt5'
]
EXTRAS_REQUIRES = {
    "develop": [
        "pytest>=6.0",
        "pytest-qt"
        "coverage",
        "pytest-cov"
    ]
}
LICENSE = 'MIT'
DESCRIPTION = 'Optimization components'
setuptools.setup(
    name="OptiBlocks",
    author="Nikita Kuklev",
    version=0.1,
    packages=setuptools.find_packages(),
    description=DESCRIPTION,
    license=LICENSE,
    long_description=LONG_DESCRIPTION,
    long_description_content_type="text/markdown",
    platforms="any",
    install_requires=INSTALL_REQUIRES,
    python_requires=">=3.8",
    extras_require=EXTRAS_REQUIRES
)
