"""GraphRAG Synthesis Engine combining ObsidianVaultIndexer, VendingMachinePaywall, and the Master Multi-Disciplinary Reasoning Prompt."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .vault_indexer import ObsidianVaultIndexer
from .vending_paywall import VendingMachinePaywall


MASTER_REASONING_PROMPT: str = (
    "Act as an advanced multi-disciplinary reasoning engine specializing in the convergence "
    "of creative systems, architectural design thinking, computational frameworks, and physical "
    "fabrication pipelines. Analyze the provided domain queries by utilizing the established "
    "lexicographical taxonomy, integrating visual resource references, executing incremental "
    "GraphRAG synthesis across craft app subdomains, and employing graphic engineering loops "
    "and hardware fabrication logic to ensure precise execution for automated synthesis."
)


class GraphRAGEngine:
    """Executes metered multi-hop GraphRAG queries across an Obsidian Vault index."""

    def __init__(
        self,
        indexer: Optional[ObsidianVaultIndexer] = None,
        paywall: Optional[VendingMachinePaywall] = None,
    ) -> None:
        self.indexer = indexer or ObsidianVaultIndexer.from_seed_vault()
        self.paywall = paywall or VendingMachinePaywall()
        self.master_prompt = MASTER_REASONING_PROMPT

    def query(
        self,
        wallet_id: str,
        query_text: str,
        max_hops: int = 2,
    ) -> Dict[str, Any]:
        """Meter the query at $0.05 ('printing prices'), traverse the Obsidian Vault subgraph,
        and synthesize a multi-disciplinary response using the Master Reasoning Prompt.
        """
        # 1. Meter query through the Stablecoin Vending Machine Paywall (raises InsufficientBalanceError if underfunded)
        receipt = self.paywall.meter_query(wallet_id=wallet_id, query_text=query_text)

        # 2. Retrieve connected multi-hop subgraph from Obsidian Vault
        subgraph = self.indexer.retrieve_subgraph(
            query_text=query_text, max_hops=max_hops
        )

        # 3. Aggregate multi-disciplinary taxonomy metadata across retrieved subgraph
        domains: List[str] = []
        craft_apps: List[str] = []
        papers: List[str] = []
        tags: List[str] = []
        note_titles: List[str] = []

        for node in subgraph["nodes"]:
            note_titles.append(node["title"])
            dom = node.get("domain")
            if dom and dom not in domains:
                domains.append(dom)
            app = node.get("craft_app")
            if app and app not in craft_apps:
                craft_apps.append(app)
            for p in node.get("papers", []):
                if p not in papers:
                    papers.append(p)
            for t in node.get("tags", []):
                if t not in tags:
                    tags.append(t)

        synthesis_text = (
            f"[Master Multi-Disciplinary Reasoning Synthesis]\n"
            f"System Prompt: {self.master_prompt}\n"
            f"Query: {query_text}\n"
            f"Seed Notes ({len(subgraph['seed_notes'])}): {', '.join(subgraph['seed_notes'])}\n"
            f"Subgraph Traversal ({max_hops}-hop): {len(subgraph['nodes'])} connected notes, "
            f"{len(subgraph['edges'])} wikilink edges.\n"
            f"Converged Craft App Subdomains: {', '.join(craft_apps) if craft_apps else 'general'}\n"
            f"Active Domains: {', '.join(domains)}\n"
            f"Referenced Research Papers ({len(papers)}): {', '.join(papers[:10])}\n"
            f"Synthesis Conclusion: Incremental GraphRAG traversal integrates {', '.join(subgraph['seed_notes'])} "
            f"across graphic engineering loops, architectural design thinking, and hardware fabrication pipelines."
        )

        wallet_state = self.paywall.get_wallet(wallet_id)

        return {
            "query": query_text,
            "master_reasoning_prompt": self.master_prompt,
            "synthesis": synthesis_text,
            "subgraph": subgraph,
            "taxonomy_summary": {
                "domains": domains,
                "craft_apps": craft_apps,
                "papers": papers,
                "tags": tags,
                "note_titles": note_titles,
            },
            "receipt": receipt.to_dict(),
            "wallet": wallet_state,
            "remaining_balance_usd": wallet_state["balance_usd"],
            "remaining_tokens": wallet_state["tokens_balance"],
        }
