from setuptools import setup, find_packages

setup(
    name="vault-graphrag-paywall",
    version="0.1.0",
    description="Cloud & Homelab Obsidian Vault GraphRAG synthesis engine with Stablecoin Vending Machine API Paywall ($0.05/query) and Per-Business VM + Docker Silos",
    author="NoJuanNobody",
    packages=find_packages(exclude=["tests*"]),
    python_requires=">=3.9",
    install_requires=[],
    extras_require={
        "dev": ["pytest>=7.0"],
    },
    entry_points={
        "console_scripts": [
            "vault-paywall=vault_graphrag_paywall.cli:main",
        ],
    },
)
