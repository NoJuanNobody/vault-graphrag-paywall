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
    AtomicTrajectoryGraphImporter,
    GraphRAGEngine,
    HomelabSiloProvisioner,
    InsufficientBalanceError,
    ObsidianVaultIndexer,
    TrajectorySanitizer,
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


def test_trajectory_sanitizer_redaction_and_provenance() -> None:
    sample_records = [
        {
            "step_index": 1,
            "source": "USER_EXPLICIT",
            "type": "USER_INPUT",
            "content": "Build repo in /Users/alejandrolondono/dev/research-ecosystem with key ghp_1234567890abcdefghijklmnopqrstuv",
        },
        {
            "step_index": 2,
            "source": "MODEL",
            "type": "PLANNER_RESPONSE",
            "content": "Implementing Paper 01 and VectorCraft in /Users/alejandrolondono/dev/research-ecosystem",
            "tool_calls": [
                {
                    "name": "write_file",
                    "args": {"Path": "/Users/alejandrolondono/dev/research-ecosystem/README.md"},
                }
            ],
        },
    ]
    sanitized, sha256_hash = TrajectorySanitizer.sanitize_records(sample_records)
    assert len(sha256_hash) == 64
    assert "/Users/alejandrolondono" not in sanitized[0]["content"]
    assert "~/dev/research-ecosystem" in sanitized[0]["content"]
    assert "[REDACTED_GITHUB_TOKEN]" in sanitized[0]["content"]
    assert sanitized[1]["tool_calls"][0]["args"]["Path"] == "~/dev/research-ecosystem/README.md"


def test_atomic_multi_note_trajectory_import_and_flat_005_query(tmp_path: Path) -> None:
    conv_id = "17f798b0-23d1-4a59-b8b6-db9226fd9023"
    logs_dir = tmp_path / "brain" / conv_id / ".system_generated" / "logs"
    logs_dir.mkdir(parents=True)
    transcript_file = logs_dir / "transcript_full.jsonl"

    records = [
        {
            "step_index": 1,
            "source": "USER_EXPLICIT",
            "type": "USER_INPUT",
            "content": "Implement research-ecosystem 36 research papers including Paper 01, Paper 13, Paper 25, VectorCraft, and CadCraft",
        },
        {
            "step_index": 2,
            "source": "MODEL",
            "type": "PLANNER_RESPONSE",
            "content": "Scaffolding Rust crates and Solidity contracts for Paper 01 and Paper 25 in /Users/alejandrolondono/dev/research-ecosystem",
            "tool_calls": [
                {"name": "write_file", "args": {"Path": "/Users/alejandrolondono/dev/research-ecosystem/Cargo.toml"}},
                {"name": "write_file", "args": {"Path": "/Users/alejandrolondono/dev/research-ecosystem/contracts/ProofOfAttribution.sol"}},
                {"name": "write_file", "args": {"Path": "/Users/alejandrolondono/dev/research-ecosystem/packages/motion_engine/src/index.ts"}},
                {"name": "run_command", "args": {"CommandLine": "cargo test --workspace"}},
            ],
        },
    ]
    transcript_file.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")

    vault_out = tmp_path / "obsidian_vault"
    indexer = ObsidianVaultIndexer.from_seed_vault()
    importer = AtomicTrajectoryGraphImporter(indexer=indexer)

    imported = importer.import_trajectory(
        f"conversation://{conv_id}",
        vault_dir=str(vault_out),
        brain_root=str(tmp_path / "brain"),
    )

    assert imported.parent_note_id == "Trajectory-17f798b0"
    assert len(imported.child_note_ids) >= 1
    assert "PAPER-01" in imported.detected_papers
    assert "PAPER-25" in imported.detected_papers
    assert "VectorCraft" in imported.detected_craft_apps
    assert "CadCraft" in imported.detected_craft_apps
    assert "research-ecosystem" in imported.detected_skills
    assert len(imported.written_files) == 1 + len(imported.child_note_ids)

    # Query the imported trajectory through GraphRAGEngine at the flat $0.05 printing price
    paywall = VendingMachinePaywall(price_per_query_usd=0.05)
    paywall.mint_tokens("agent-buyer", usd_amount=0.10)
    engine = GraphRAGEngine(indexer=indexer, paywall=paywall)

    res = engine.query("agent-buyer", "Trajectory-17f798b0 research-ecosystem Paper 01 ProofOfAttribution", max_hops=2)
    assert res["receipt"]["cost_usd"] == 0.05
    assert res["receipt"]["pricing_tier"] == "printing_prices_$0.05"
    assert res["remaining_balance_usd"] == 0.05
    assert any("Trajectory-17f798b0" in title for title in res["taxonomy_summary"]["note_titles"])


def test_cli_import_trajectory_and_batch_scanner(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    conv_id = "abcdef12-3456-7890-abcd-ef1234567890"
    logs_dir = tmp_path / "brain" / conv_id / ".system_generated" / "logs"
    logs_dir.mkdir(parents=True)
    transcript_file = logs_dir / "transcript_full.jsonl"
    transcript_file.write_text(
        json.dumps(
            {
                "step_index": 1,
                "source": "USER_EXPLICIT",
                "type": "USER_INPUT",
                "content": "Build tmux-agent-fleet and Paper 15 with DesignCraft",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    rc_single = cli_main(
        [
            "import-trajectory",
            str(transcript_file),
            "--query",
            "Trajectory-abcdef12 tmux-agent-fleet Paper 15",
        ]
    )
    assert rc_single == 0
    out_single = json.loads(capsys.readouterr().out)
    assert out_single["imported_trajectory"]["parent_note_id"] == "Trajectory-abcdef12"
    assert out_single["metered_query_result"]["receipt"]["cost_usd"] == 0.05

    rc_batch = cli_main(
        [
            "import-trajectories",
            "--brain-root",
            str(tmp_path / "brain"),
            "--limit",
            "5",
        ]
    )
    assert rc_batch == 0
    out_batch = json.loads(capsys.readouterr().out)
    assert out_batch["imported_count"] == 1

