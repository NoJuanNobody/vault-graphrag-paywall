---
name: vault-graphrag-paywall
description: Cloud and Homelab Obsidian Vault GraphRAG synthesis engine with a Stablecoin Tokenized "Vending Machine" API Paywall ($0.05 per query) and Per-Business Siloed VM + nested Docker isolation. Use when indexing Obsidian vaults (~200+ papers/notes, 36 research papers, 15 ArtCraft apps, Graphic Engineering loops, architecture, design thinking, PCB/3D fabrication), executing metered multi-disciplinary GraphRAG queries, or provisioning isolated homelab business silos (~$130 Mini PC + 10TB external drive).
---

# Vault GraphRAG Paywall (`vault-graphrag-paywall`)

An end-to-end **Obsidian Vault GraphRAG Synthesis Engine**, **Stablecoin Tokenized "Vending Machine" API Paywall** (`$0.05` "printing prices" per query), and **Homelab Per-Business Siloed VM + Docker Provisioner**.

## Overview

1. **Cloud & Homelab Obsidian Vault GraphRAG Engine**:
   - Parses Obsidian Markdown vaults (`~200+` papers & notes, `36` core research papers, `15` ArtCraft suite domain apps, Graphic Engineering loops, architecture PDFs, design thinking frameworks, 3D/PCB hardware fabrication pipelines, and quantum Orch-OR notes).
   - Extracts `[[wikilinks]]`, `#tags`, and YAML frontmatter (`domain`, `papers`, `craft_app`) into an entity-relationship adjacency graph (`nodes` and `edges`).
   - Performs multi-hop subgraph traversal (`max_hops`) and applies the **Master Multi-Disciplinary Reasoning Prompt** for automated synthesis.

2. **Stablecoin Tokenized "Vending Machine" API Paywall**:
   - Models a frictionless API vending machine where clients deposit stablecoins (USDC/USDT) to mint query credits or pay per-request at **$0.05 ("printing prices")** per query.
   - Issues cryptographic HMAC-SHA256 receipts (`QueryReceipt`) verifying wallet deduction, query hash, timestamp, and remaining balance.
   - Rejects unauthenticated or insufficient-balance requests (`InsufficientBalanceError`).

3. **Homelab Per-Business Siloed VM + Nested Docker Isolation**:
   - Models an ultra-low-cost room homelab server (**~$130 Mini PC** with Intel N100/Ryzen CPU + **10TB External Drive**).
   - Allocates strictly isolated **Per-Business Virtual Machines (`VMSiloSpec`)** with dedicated vCPU, RAM, encrypted ZFS/ext4 storage slices on the 10TB array, and isolated VLANs.
   - Generates nested **Docker Compose** stacks inside each business VM (`API_PORT=8001`, `WEB_PORT=3001`) so each client business's vault graph, SQLite ledger, and vector/graph index remain 100% physically and logically segregated.

---

## Master Multi-Disciplinary Reasoning Prompt

Every metered synthesis execution applies the canonical **Master Multi-Disciplinary Reasoning Prompt**:

> "Act as an advanced multi-disciplinary reasoning engine specializing in the convergence of creative systems, architectural design thinking, computational frameworks, and physical fabrication pipelines. Analyze the provided domain queries by utilizing the established lexicographical taxonomy, integrating visual resource references, executing incremental GraphRAG synthesis across craft app subdomains, and employing graphic engineering loops and hardware fabrication logic to ensure precise execution for automated synthesis."

---

## Quickstart & CLI Usage

### Installation

```bash
pip install -e .
```

Or install via the Skills CLI:

```bash
npx skills add NoJuanNobody/vault-graphrag-paywall -g
```

### CLI Commands

```bash
# 1. Index the built-in seed Obsidian Vault (or pass --vault-dir /path/to/vault)
vault-paywall index

# 2. Mint stablecoin tokens into a client wallet ($1.00 = 20 queries @ $0.05/query)
vault-paywall vending-mint --wallet client-alpha --usd 1.00

# 3. Run a metered GraphRAG synthesis query ($0.05 deducted, HMAC receipt returned)
vault-paywall query --wallet client-alpha --query "How do ArtCraft apps integrate with Graphic Engineering loops and PCB fabrication?" --hops 2

# 4. Generate a Homelab Per-Business VM Silo + Docker Compose configuration
vault-paywall homelab-spec --business-id acme-design-studio --storage-gb 500 --port 8001

# 5. Run the complete end-to-end JSON demonstration
vault-paywall demo
```

---

## Python API Usage

```python
from vault_graphrag_paywall import (
    ObsidianVaultIndexer,
    VendingMachinePaywall,
    GraphRAGEngine,
    HomelabSiloProvisioner,
)

# 1. Load & index seed vault (36 papers, 15 ArtCraft apps, architecture, PCB, Orch-OR)
indexer = ObsidianVaultIndexer.from_seed_vault()

# 2. Initialize Stablecoin Vending Machine Paywall ($0.05 per query)
paywall = VendingMachinePaywall(price_per_query_usd=0.05)
paywall.mint_tokens(wallet_id="studio-01", usd_amount=0.50)  # 10 queries

# 3. Execute metered multi-hop GraphRAG query
engine = GraphRAGEngine(indexer=indexer, paywall=paywall)
result = engine.query(
    wallet_id="studio-01",
    query_text="Synthesize VectorCraft, CadCraft, and PCB hardware fabrication loops",
    max_hops=2,
)

print(result["synthesis"])
print("Receipt Signature:", result["receipt"]["signature"])
print("Remaining USD:", result["wallet"]["balance_usd"])

# 4. Provision Homelab VM Silo + nested Docker Compose
provisioner = HomelabSiloProvisioner()
vm_spec = provisioner.provision_vm_silo("studio-01", storage_gb=1000, api_port=8001, web_port=3001)
compose_yaml = provisioner.generate_docker_compose("studio-01", port=8001, web_port=3001)
```
