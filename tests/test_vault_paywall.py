"""Comprehensive pytest suite for vault-graphrag-paywall."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from vault_graphrag_paywall import (
    ARTCRAFT_APPS,
    DEFAULT_PRICE_PER_QUERY_USD,
    MASTER_REASONING_PROMPT,
    GraphRAGEngine,
    HomelabSiloProvisioner,
    InsufficientBalanceError,
    ObsidianVaultIndexer,
    VendingMachinePaywall,
)
from vault_graphrag_paywall.cli import main as cli_main


def test_markdown_parsing_wikilinks_tags_and_frontmatter() -> None:
    raw_md = """---
title: Hybrid Perspective & PCB Synth
domain: hardware-fabrication
craft_app: CadCraft
papers: [PAPER-01, PAPER-10]
tags: [frontmatter-tag]
---
Connecting [[Graphic-Engineering-Loop|Graphic Loop]] with [[PCB-Fabrication-Pipeline#routing]] and [[VectorCraft-Precision-Paths]].
Inline tags: #pcb-design #artcraft/cad
"""
    note = ObsidianVaultIndexer.parse_markdown("Hybrid-Perspective-PCB", raw_md)
    assert note.note_id == "Hybrid-Perspective-PCB"
    assert note.title == "Hybrid Perspective & PCB Synth"
    assert note.domain == "hardware-fabrication"
    assert note.craft_app == "CadCraft"
    assert note.papers == ["PAPER-01", "PAPER-10"]
    assert "Graphic-Engineering-Loop" in note.wikilinks
    assert "PCB-Fabrication-Pipeline" in note.wikilinks
    assert "VectorCraft-Precision-Paths" in note.wikilinks
    assert "frontmatter-tag" in note.tags
    assert "pcb-design" in note.tags
    assert "artcraft/cad" in note.tags


def test_index_directory_tree(tmp_path: Path) -> None:
    sub = tmp_path / "subfolder"
    sub.mkdir()
    (tmp_path / "NoteA.md").write_text(
        "---\ndomain: architecture\ncraft_app: DesignCraft\n---\nLinks to [[NoteB]] #arch\n",
        encoding="utf-8",
    )
    (sub / "NoteB.md").write_text(
        "---\ndomain: creative-systems\ncraft_app: VectorCraft\n---\nBacklink to [[NoteA]] #vec\n",
        encoding="utf-8",
    )

    indexer = ObsidianVaultIndexer()
    graph = indexer.index_directory(tmp_path)
    assert graph["stats"]["indexed_notes_count"] == 2
    assert graph["stats"]["edges_count"] == 2
    assert set(graph["stats"]["unique_craft_apps"]) == {"DesignCraft", "VectorCraft"}


def test_seed_vault_covers_36_papers_15_artcraft_apps_and_core_domains() -> None:
    indexer = ObsidianVaultIndexer.from_seed_vault()
    graph = indexer.get_graph()

    assert graph["stats"]["indexed_notes_count"] >= 18
    assert graph["stats"]["unique_papers_count"] == 36
    assert set(graph["stats"]["unique_craft_apps"]) == set(ARTCRAFT_APPS)
    assert len(ARTCRAFT_APPS) == 15
    assert "Graphic-Engineering-Loop" in graph["nodes"]
    assert "PCB-Fabrication-Pipeline" in graph["nodes"]
    assert "Architectural-Design-Thinking" in graph["nodes"]
    assert "Quantum-Orch-OR-Consciousness" in graph["nodes"]


def test_multihop_subgraph_retrieval() -> None:
    indexer = ObsidianVaultIndexer.from_seed_vault()
    sub_1hop = indexer.retrieve_subgraph("Quantum-Orch-OR-Consciousness", max_hops=1)
    sub_2hop = indexer.retrieve_subgraph("Quantum-Orch-OR-Consciousness", max_hops=2)

    assert "Quantum-Orch-OR-Consciousness" in sub_1hop["seed_notes"]
    assert len(sub_2hop["nodes"]) >= len(sub_1hop["nodes"])
    assert len(sub_2hop["edges"]) >= len(sub_1hop["edges"])


def test_vending_machine_mint_tokens_printing_prices() -> None:
    paywall = VendingMachinePaywall()
    assert paywall.price_per_query_usd == DEFAULT_PRICE_PER_QUERY_USD == 0.05

    mint_res = paywall.mint_tokens(wallet_id="wallet-01", usd_amount=1.00, stablecoin="USDC")
    assert mint_res["deposited_usd"] == 1.00
    assert mint_res["minted_tokens"] == 20
    assert mint_res["balance_usd"] == 1.00
    assert mint_res["tokens_balance"] == 20


def test_vending_machine_query_deduction_and_receipt_verification() -> None:
    paywall = VendingMachinePaywall(price_per_query_usd=0.05)
    paywall.mint_tokens(wallet_id="wallet-02", usd_amount=0.15)  # 3 queries

    receipt = paywall.meter_query("wallet-02", "CadCraft PCB enclosure synthesis")
    assert receipt.cost_usd == 0.05
    assert receipt.tokens_deducted == 1
    assert receipt.remaining_balance_usd == 0.10
    assert receipt.remaining_tokens == 2
    assert paywall.verify_receipt(receipt) is True

    # Tamper with receipt and verify signature fails
    tampered = receipt.to_dict()
    tampered["remaining_balance_usd"] = 999.00
    assert paywall.verify_receipt(tampered) is False


def test_vending_machine_insufficient_balance_rejection() -> None:
    paywall = VendingMachinePaywall(price_per_query_usd=0.05)
    # Unfunded wallet fails immediately
    with pytest.raises(InsufficientBalanceError):
        paywall.meter_query("empty-wallet", "Attempt free query")

    # Fund for exactly 1 query ($0.05), second query must raise InsufficientBalanceError
    paywall.mint_tokens("single-query-wallet", usd_amount=0.05)
    paywall.meter_query("single-query-wallet", "First valid query")
    with pytest.raises(InsufficientBalanceError):
        paywall.meter_query("single-query-wallet", "Second query with $0.00 balance")


def test_graphrag_engine_end_to_end_query_and_master_prompt() -> None:
    indexer = ObsidianVaultIndexer.from_seed_vault()
    paywall = VendingMachinePaywall(price_per_query_usd=0.05)
    paywall.mint_tokens("creative-lab", usd_amount=0.50)

    engine = GraphRAGEngine(indexer=indexer, paywall=paywall)
    response = engine.query(
        wallet_id="creative-lab",
        query_text="Graphic Engineering Loop with VectorCraft, CadCraft, and PCB fabrication",
        max_hops=2,
    )

    assert response["master_reasoning_prompt"] == MASTER_REASONING_PROMPT
    assert "lexicographical taxonomy" in response["master_reasoning_prompt"]
    assert "incremental GraphRAG synthesis across craft app subdomains" in response["master_reasoning_prompt"]
    assert response["remaining_balance_usd"] == 0.45
    assert response["remaining_tokens"] == 9
    assert paywall.verify_receipt(response["receipt"]) is True
    assert len(response["subgraph"]["nodes"]) >= 3
    assert "CadCraft" in response["taxonomy_summary"]["craft_apps"]


def test_homelab_silo_vm_provisioning_and_isolation() -> None:
    provisioner = HomelabSiloProvisioner(host_cost_usd=130.0, total_storage_tb=10.0)
    silo_a = provisioner.provision_vm_silo("Business Alpha", storage_gb=1000, api_port=8001, web_port=3001)
    silo_b = provisioner.provision_vm_silo("Business Beta", storage_gb=1500, api_port=8001, web_port=3001)

    assert silo_a.business_id == "business-alpha"
    assert silo_b.business_id == "business-beta"
    assert silo_a.vlan_id != silo_b.vlan_id
    assert silo_a.subnet_cidr != silo_b.subnet_cidr
    assert silo_a.storage_mount_path != silo_b.storage_mount_path
    assert provisioner.allocated_storage_gb == 2500
    assert provisioner.available_storage_gb == 7500

    # Exceeding remaining 10TB external drive capacity raises ValueError
    with pytest.raises(ValueError):
        provisioner.provision_vm_silo("Oversized Tenant", storage_gb=8000)


def test_homelab_nested_docker_compose_generation() -> None:
    provisioner = HomelabSiloProvisioner()
    compose_yaml = provisioner.generate_docker_compose(
        business_id="soop-studio", port=8001, web_port=3001, storage_gb=500
    )
    assert "vault-graphrag-api-soop-studio" in compose_yaml
    assert "8001:8001" in compose_yaml
    assert "3001:3001" in compose_yaml
    assert "/mnt/homelab-10tb-vaults/silos/soop-studio/obsidian-vault" in compose_yaml
    assert "VENDING_PRICE_USD=0.05" in compose_yaml


def test_cli_subcommands_execution(capsys: pytest.CaptureFixture[str]) -> None:
    # 1. demo subcommand
    rc_demo = cli_main(["demo"])
    assert rc_demo == 0
    out_demo = json.loads(capsys.readouterr().out)
    assert out_demo["status"] == "ok"
    assert out_demo["metered_query_result"]["receipt_verified"] is True

    # 2. homelab-spec subcommand
    rc_silo = cli_main(["homelab-spec", "--business-id", "tenant-x", "--storage-gb", "400", "--port", "8001"])
    assert rc_silo == 0
    out_silo = json.loads(capsys.readouterr().out)
    assert out_silo["vm_silo_spec"]["business_id"] == "tenant-x"
    assert out_silo["vm_silo_spec"]["api_port"] == 8001
