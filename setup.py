from setuptools import setup


setup(
    name="omni-asset-cli",
    version="0.1.0",
    description="Unified CLI for Stage 1 furniture and prop OpenUSD validation with NVIDIA Omniverse Asset Validator",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    python_requires=">=3.10",
    py_modules=["omni_asset_cli"],
    packages=["omni_asset_service"],
    entry_points={
        "console_scripts": [
            "omni-asset-cli=omni_asset_cli:main",
            "omni-asset-service=omni_asset_service.__main__:main",
        ],
    },
    extras_require={
        "validator": ["omniverse-asset-validator[usd,numpy]"],
        "api": ["fastapi>=0.110,<1", "uvicorn[standard]>=0.27,<1", "python-multipart>=0.0.9,<1"],
    },
)
