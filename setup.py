from setuptools import setup


setup(
    name="omni-asset-cli",
    version="0.1.0",
    description="Unified CLI for validating OpenUSD assets with NVIDIA Omniverse Asset Validator",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    python_requires=">=3.10",
    py_modules=["omni_asset_cli"],
    entry_points={
        "console_scripts": [
            "omni-asset-cli=omni_asset_cli:main",
        ],
    },
    extras_require={
        "validator": ["omniverse-asset-validator[usd,numpy]"],
    },
)

