"""Command-line interface for vault-graphrag-paywall."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Optional

from .graphrag_engine import GraphRAGEngine, MASTER_REASONING_PROMPT
from .homelab_silo import HomelabSiloProvisioner
from .trajectory_importer import AtomicTrajectoryGraphImporter
from .vault_indexer import ObsidianVaultIndexer
from .vending_paywall import VendingMachinePaywall


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vault-paywall",
        description="Obsidian Vault GraphRAG Synthesis Engine + $0.05 Stablecoin Vending Machine Paywall + Homelab VM Silo Provisioner",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 1. index
    index_p = subparsers.add_parser(
        "index", help="Index an Obsidian Vault directory or the built-in seed vault"
    )
    index_p.add_argument(
        "--vault-dir",
        type=str,
        default=None,
        help="Optional path to an Obsidian Vault folder (defaults to built-in seed vault)",
    )

    # 2. vending-mint
    mint_p = subparsers.add_parser(
        "vending-mint",
        help="Mint query tokens into a client wallet ($0.05 'printing prices' per query)",
    )
    mint_p.add_argument("--wallet", type=str, default="demo-client", help="Wallet ID")
    mint_p.add_argument(
        "--usd", type=float, default=1.00, help="Stablecoin USD amount to deposit"
    )
    mint_p.add_argument(
        "--stablecoin", type=str, default="USDC", help="Stablecoin symbol (USDC/USDT)"
    )

    # 3. query
    query_p = subparsers.add_parser(
        "query",
        help="Execute a metered $0.05 multi-hop GraphRAG synthesis query",
    )
    query_p.add_argument("--wallet", type=str, default="demo-client", help="Wallet ID")
    query_p.add_argument(
        "--usd",
        type=float,
        default=0.50,
        help="Initial wallet funding in USD before running CLI query",
    )
    query_p.add_argument(
        "--query",
        type=str,
        required=True,
        help="Multi-disciplinary domain query string",
    )
    query_p.add_argument(
        "--hops", type=int, default=2, help="Maximum graph traversal hops"
    )

    # 4. homelab-spec
    silo_p = subparsers.add_parser(
        "homelab-spec",
        help="Generate Per-Business Siloed VM specification & nested Docker Compose stack",
    )
    silo_p.add_argument(
        "--business-id",
        type=str,
        default="studio-alpha",
        help="Business identifier for VM & Docker silo",
    )
    silo_p.add_argument(
        "--storage-gb",
        type=int,
        default=500,
        help="Dedicated slice on the 10TB external drive (in GB)",
    )
    silo_p.add_argument(
        "--port", type=int, default=8001, help="Dedicated API port inside silo"
    )
    silo_p.add_argument(
        "--web-port", type=int, default=3001, help="Dedicated Web port inside silo"
    )

    # 5. import-trajectory (Single-session Atomic Multi-Note Graph importer)
    imp_p = subparsers.add_parser(
        "import-trajectory",
        help="Import a single agent trajectory (conversation://<id> or transcript.jsonl) as an Atomic Multi-Note Graph with deterministic redaction and SHA-256 provenance",
    )
    imp_p.add_argument(
        "target",
        type=str,
        help="Conversation ID (e.g. conversation://17f798b0-...) or path to transcript.jsonl",
    )
    imp_p.add_argument(
        "--vault-dir",
        type=str,
        default=None,
        help="Optional Obsidian Vault directory to write atomic Markdown notes into",
    )
    imp_p.add_argument(
        "--query",
        type=str,
        default=None,
        help="Optional immediate $0.05 metered GraphRAG query to run against the imported trajectory",
    )

    # 6. import-trajectories (Batch Brain Scanner)
    batch_p = subparsers.add_parser(
        "import-trajectories",
        help="Batch-scan ~/.gemini/antigravity-cli/brain/* and import recent trajectories into the Obsidian Vault GraphRAG index",
    )
    batch_p.add_argument(
        "--brain-root",
        type=str,
        default=None,
        help="Path to brain root directory (defaults to ~/.gemini/antigravity-cli/brain)",
    )
    batch_p.add_argument(
        "--vault-dir",
        type=str,
        default=None,
        help="Optional Obsidian Vault directory to write atomic Markdown notes into",
    )
    batch_p.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of recent conversations to import",
    )

    # 7. demo
    subparsers.add_parser(
        "demo",
        help="Run an end-to-end JSON demonstration of vault indexing, token minting, GraphRAG query, and homelab VM silo provisioning",
    )

    return parser


def run_demo() -> Dict[str, Any]:
    """Execute a complete end-to-end demonstration returning structured JSON data."""
    indexer = ObsidianVaultIndexer.from_seed_vault()
    graph = indexer.get_graph()

    paywall = VendingMachinePaywall(price_per_query_usd=0.05)
    mint_info = paywall.mint_tokens(wallet_id="atelier-nexus", usd_amount=0.25)

    engine = GraphRAGEngine(indexer=indexer, paywall=paywall)
    query_result = engine.query(
        wallet_id="atelier-nexus",
        query_text="Synthesize Graphic Engineering Loop with CadCraft, VectorCraft, PCB fabrication, and Architectural Design Thinking",
        max_hops=2,
    )

    provisioner = HomelabSiloProvisioner()
    vm_spec = provisioner.provision_vm_silo(
        business_id="atelier-nexus",
        storage_gb=1000,
        api_port=8001,
        web_port=3001,
    )
    compose_yaml = provisioner.generate_docker_compose(
        business_id="atelier-nexus", port=8001, web_port=3001
    )

    return {
        "status": "ok",
        "vault_stats": graph["stats"],
        "vending_mint": mint_info,
        "metered_query_result": {
            "query": query_result["query"],
            "master_reasoning_prompt": MASTER_REASONING_PROMPT,
            "seed_notes": query_result["subgraph"]["seed_notes"],
            "subgraph_nodes_count": len(query_result["subgraph"]["nodes"]),
            "subgraph_edges_count": len(query_result["subgraph"]["edges"]),
            "taxonomy_summary": query_result["taxonomy_summary"],
            "receipt": query_result["receipt"],
            "receipt_verified": paywall.verify_receipt(query_result["receipt"]),
            "remaining_balance_usd": query_result["remaining_balance_usd"],
            "remaining_tokens": query_result["remaining_tokens"],
        },
        "homelab_silo": {
            "vm_spec": vm_spec.to_dict(),
            "hardware_summary": provisioner.get_hardware_summary(),
            "docker_compose_preview": compose_yaml.splitlines()[:15],
        },
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "index":
        indexer = ObsidianVaultIndexer()
        if args.vault_dir:
            graph = indexer.index_directory(args.vault_dir)
        else:
            indexer.load_seed_vault()
            graph = indexer.get_graph()
        print(json.dumps(graph["stats"], indent=2))
        return 0

    if args.command == "vending-mint":
        paywall = VendingMachinePaywall(price_per_query_usd=0.05)
        result = paywall.mint_tokens(
            wallet_id=args.wallet, usd_amount=args.usd, stablecoin=args.stablecoin
        )
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "query":
        indexer = ObsidianVaultIndexer.from_seed_vault()
        paywall = VendingMachinePaywall(price_per_query_usd=0.05)
        paywall.mint_tokens(wallet_id=args.wallet, usd_amount=args.usd)
        engine = GraphRAGEngine(indexer=indexer, paywall=paywall)
        result = engine.query(
            wallet_id=args.wallet, query_text=args.query, max_hops=args.hops
        )
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "homelab-spec":
        provisioner = HomelabSiloProvisioner()
        spec = provisioner.provision_vm_silo(
            business_id=args.business_id,
            storage_gb=args.storage_gb,
            api_port=args.port,
            web_port=args.web_port,
        )
        compose = provisioner.generate_docker_compose(
            business_id=args.business_id,
            port=args.port,
            web_port=args.web_port,
            storage_gb=args.storage_gb,
        )
        output = {
            "vm_silo_spec": spec.to_dict(),
            "docker_compose": compose,
            "hardware_summary": provisioner.get_hardware_summary(),
        }
        print(json.dumps(output, indent=2))
        return 0

    if args.command == "import-trajectory":
        indexer = ObsidianVaultIndexer.from_seed_vault()
        importer = AtomicTrajectoryGraphImporter(indexer=indexer)
        imported = importer.import_trajectory(
            args.target, vault_dir=args.vault_dir
        )
        payload: Dict[str, Any] = {
            "imported_trajectory": imported.to_dict(),
            "vault_stats": indexer.get_graph()["stats"],
        }
        if args.query:
            paywall = VendingMachinePaywall(price_per_query_usd=0.05)
            paywall.mint_tokens(wallet_id="trajectory-client", usd_amount=0.25)
            engine = GraphRAGEngine(indexer=indexer, paywall=paywall)
            payload["metered_query_result"] = engine.query(
                wallet_id="trajectory-client", query_text=args.query, max_hops=2
            )
        print(json.dumps(payload, indent=2))
        return 0

    if args.command == "import-trajectories":
        indexer = ObsidianVaultIndexer.from_seed_vault()
        importer = AtomicTrajectoryGraphImporter(indexer=indexer)
        batch = importer.import_all_recent(
            brain_root=args.brain_root,
            vault_dir=args.vault_dir,
            limit=args.limit,
        )
        payload = {
            "imported_count": len(batch),
            "trajectories": [b.to_dict() for b in batch],
            "vault_stats": indexer.get_graph()["stats"],
        }
        print(json.dumps(payload, indent=2))
        return 0

    if args.command == "demo":
        print(json.dumps(run_demo(), indent=2))
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
