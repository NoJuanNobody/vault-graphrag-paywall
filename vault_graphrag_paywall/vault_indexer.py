"""Obsidian Vault Markdown parser, entity-relationship adjacency graph builder, and seed vault loader."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
TAG_RE = re.compile(r"(?:^|\s)#([a-zA-Z0-9_\-/]+)")
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)

# 15 ArtCraft domain applications
ARTCRAFT_APPS: List[str] = [
    "VectorCraft",
    "PhotoCraft",
    "LightCraft",
    "DesignCraft",
    "FilmCraft",
    "EffectCraft",
    "SoundCraft",
    "CadCraft",
    "FigCraft",
    "DeckCraft",
    "GridCraft",
    "WordCraft",
    "PdfCraft",
    "ScriptCraft",
    "InkDraw",
]

# 36 Core Research Papers in the Obsidian Vault Corpus
RESEARCH_PAPERS_36: List[str] = [
    f"PAPER-{i:02d}: Multi-Disciplinary Synthesis & GraphRAG Study #{i}"
    for i in range(1, 37)
]


@dataclass
class VaultNote:
    """Represents a parsed Markdown note inside an Obsidian Vault."""

    note_id: str
    title: str
    content: str
    domain: str = "general"
    papers: List[str] = field(default_factory=list)
    craft_app: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    wikilinks: List[str] = field(default_factory=list)
    frontmatter: Dict[str, Any] = field(default_factory=dict)
    path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _parse_simple_yaml(yaml_block: str) -> Dict[str, Any]:
    """Lightweight parser for Obsidian YAML frontmatter without external dependencies."""
    data: Dict[str, Any] = {}
    current_list_key: Optional[str] = None

    for raw_line in yaml_block.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("- ") and current_list_key:
            item = line[2:].strip().strip("'\"")
            data.setdefault(current_list_key, []).append(item)
            continue

        if ":" in line:
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip()
            current_list_key = None

            if not val:
                current_list_key = key
                data[key] = []
            elif val.startswith("[") and val.endswith("]"):
                inner = val[1:-1].strip()
                if not inner:
                    data[key] = []
                else:
                    data[key] = [
                        x.strip().strip("'\"") for x in inner.split(",") if x.strip()
                    ]
            else:
                cleaned = val.strip("'\"")
                if cleaned.isdigit():
                    data[key] = int(cleaned)
                else:
                    data[key] = cleaned
    return data


class ObsidianVaultIndexer:
    """Indexes an Obsidian Vault into an entity-relationship graph of notes, wikilinks, tags, and domains."""

    def __init__(self) -> None:
        self.nodes: Dict[str, VaultNote] = {}
        self.edges: List[Dict[str, str]] = []
        self.adjacency: Dict[str, Set[str]] = {}
        self.corpus_metadata: Dict[str, Any] = {
            "total_corpus_capacity_notes": 212,
            "research_papers_count": len(RESEARCH_PAPERS_36),
            "artcraft_apps_count": len(ARTCRAFT_APPS),
        }

    @staticmethod
    def parse_markdown(
        note_id: str, raw_markdown: str, path: Optional[str] = None
    ) -> VaultNote:
        """Parse a Markdown string to extract YAML frontmatter, [[wikilinks]], and #tags."""
        frontmatter: Dict[str, Any] = {}
        body = raw_markdown

        fm_match = FRONTMATTER_RE.match(raw_markdown)
        if fm_match:
            frontmatter = _parse_simple_yaml(fm_match.group(1))
            body = raw_markdown[fm_match.end() :]

        # Extract [[wikilinks]]
        wikilinks: List[str] = []
        for match in WIKILINK_RE.finditer(body):
            target = match.group(1).strip()
            if target and target not in wikilinks:
                wikilinks.append(target)

        # Extract #tags from body and frontmatter
        tags: List[str] = []
        fm_tags = frontmatter.get("tags", [])
        if isinstance(fm_tags, str):
            fm_tags = [fm_tags]
        for t in fm_tags:
            if t not in tags:
                tags.append(str(t))

        for match in TAG_RE.finditer(body):
            tag = match.group(1).strip()
            if tag and tag not in tags:
                tags.append(tag)

        title = str(frontmatter.get("title", note_id))
        domain = str(frontmatter.get("domain", "general"))
        craft_app = frontmatter.get("craft_app")
        if craft_app is not None:
            craft_app = str(craft_app)

        papers_raw = frontmatter.get("papers", [])
        if isinstance(papers_raw, str):
            papers = [papers_raw]
        elif isinstance(papers_raw, list):
            papers = [str(p) for p in papers_raw]
        else:
            papers = []

        return VaultNote(
            note_id=note_id,
            title=title,
            content=body.strip(),
            domain=domain,
            papers=papers,
            craft_app=craft_app,
            tags=tags,
            wikilinks=wikilinks,
            frontmatter=frontmatter,
            path=path,
        )

    def add_note(self, note: VaultNote) -> None:
        """Add a VaultNote to the graph and rebuild adjacency edges."""
        self.nodes[note.note_id] = note
        self.adjacency.setdefault(note.note_id, set())

        for target in note.wikilinks:
            self.adjacency.setdefault(target, set())
            self.adjacency[note.note_id].add(target)
            self.adjacency[target].add(note.note_id)
            edge = {
                "source": note.note_id,
                "target": target,
                "relation": "wikilink",
            }
            if edge not in self.edges:
                self.edges.append(edge)

    def add_markdown_note(
        self, note_id: str, raw_markdown: str, path: Optional[str] = None
    ) -> VaultNote:
        """Parse and add a Markdown note to the vault index."""
        note = self.parse_markdown(note_id=note_id, raw_markdown=raw_markdown, path=path)
        self.add_note(note)
        return note

    def index_directory(self, vault_dir: str | Path) -> Dict[str, Any]:
        """Recursively scan a directory tree for .md files and build the entity-relationship graph."""
        root = Path(vault_dir)
        if not root.exists():
            raise FileNotFoundError(f"Vault directory not found: {vault_dir}")

        for md_file in sorted(root.rglob("*.md")):
            if any(part.startswith(".") for part in md_file.parts):
                continue
            note_id = md_file.stem
            raw_text = md_file.read_text(encoding="utf-8")
            self.add_markdown_note(note_id=note_id, raw_markdown=raw_text, path=str(md_file))

        return self.get_graph()

    def get_graph(self) -> Dict[str, Any]:
        """Return the serialized entity-relationship graph (`nodes`, `edges`, and `stats`)."""
        all_papers: Set[str] = set()
        all_craft_apps: Set[str] = set()
        all_domains: Set[str] = set()
        all_tags: Set[str] = set()

        for note in self.nodes.values():
            all_domains.add(note.domain)
            for p in note.papers:
                all_papers.add(p)
            if note.craft_app:
                all_craft_apps.add(note.craft_app)
            for t in note.tags:
                all_tags.add(t)

        return {
            "nodes": {nid: note.to_dict() for nid, note in self.nodes.items()},
            "edges": list(self.edges),
            "stats": {
                "indexed_notes_count": len(self.nodes),
                "edges_count": len(self.edges),
                "unique_domains": sorted(all_domains),
                "unique_craft_apps": sorted(all_craft_apps),
                "unique_papers_count": len(all_papers),
                "unique_tags_count": len(all_tags),
                "total_vault_corpus_capacity": self.corpus_metadata["total_corpus_capacity_notes"],
            },
        }

    def retrieve_subgraph(self, query_text: str, max_hops: int = 2) -> Dict[str, Any]:
        """Retrieve a multi-hop subgraph of VaultNotes matching the query terms and their linked neighbors."""
        tokens = [
            tok.lower()
            for tok in re.findall(r"[a-zA-Z0-9_\-]+", query_text)
            if len(tok) >= 2
        ]

        scored_seeds: List[Tuple[int, str]] = []
        for note_id, note in self.nodes.items():
            haystack = " ".join(
                [
                    note.note_id,
                    note.title,
                    note.domain,
                    note.craft_app or "",
                    " ".join(note.tags),
                    " ".join(note.papers),
                    note.content,
                ]
            ).lower()
            score = sum(1 for tok in tokens if tok in haystack)
            if score > 0:
                scored_seeds.append((score, note_id))

        scored_seeds.sort(key=lambda item: (-item[0], item[1]))
        seed_ids = [nid for _, nid in scored_seeds[:5]]

        # Fallback to top central nodes if query has no direct lexical match
        if not seed_ids and self.nodes:
            seed_ids = sorted(self.nodes.keys())[:3]

        visited: Dict[str, int] = {nid: 0 for nid in seed_ids}
        frontier: List[Tuple[str, int]] = [(nid, 0) for nid in seed_ids]

        while frontier:
            current_id, depth = frontier.pop(0)
            if depth >= max_hops:
                continue
            for neighbor_id in sorted(self.adjacency.get(current_id, set())):
                if neighbor_id in self.nodes and neighbor_id not in visited:
                    visited[neighbor_id] = depth + 1
                    frontier.append((neighbor_id, depth + 1))

        subgraph_nodes = [
            self.nodes[nid].to_dict() for nid in visited if nid in self.nodes
        ]
        subgraph_edges = [
            edge
            for edge in self.edges
            if edge["source"] in visited and edge["target"] in visited
        ]

        return {
            "seed_notes": seed_ids,
            "max_hops": max_hops,
            "hop_distances": visited,
            "nodes": subgraph_nodes,
            "edges": subgraph_edges,
        }

    def load_seed_vault(self) -> "ObsidianVaultIndexer":
        """Populate the indexer with the multi-disciplinary seed vault:
        - 36 research papers distributed across core domain notes
        - All 15 ArtCraft suite apps
        - Graphic Engineering loops, Architectural Design Thinking, 3D/PCB Fabrication, Quantum Orch-OR
        """
        seed_notes = [
            (
                "Graphic-Engineering-Loop",
                """---
title: Graphic Engineering Loop & Hybrid Perspective Pipeline
domain: creative-systems
craft_app: InkDraw
papers: [PAPER-01, PAPER-02, PAPER-03, PAPER-04]
tags: [graphic-engineering, ink-draw, perspective-blockout, dirty-gradient]
---
The [[Graphic-Engineering-Loop]] converges 3D perspective underlays from [[CadCraft-3D-Blockout]] and [[VectorCraft-Precision-Paths]] with GenAI brush ink and SOOP dirty-gradient color passes in [[PhotoCraft-Compositor]] and [[LightCraft-Color-Grading]].
It enforces continuity verification across [[ScriptCraft-Narrative-Engine]] and [[DesignCraft-Layout-System]].
#continuity #shader-pipeline #artcraft
""",
            ),
            (
                "VectorCraft-Precision-Paths",
                """---
title: VectorCraft Precision Bezier & SVG Fabrication Paths
domain: artcraft-suite
craft_app: VectorCraft
papers: [PAPER-05, PAPER-06]
tags: [vectorcraft, bezier, svg, plotter, cad-bridge]
---
[[VectorCraft-Precision-Paths]] generates deterministic vector geometry linking [[Graphic-Engineering-Loop]] with [[PCB-Fabrication-Pipeline]] and [[CadCraft-3D-Blockout]].
Exports clean DXF/SVG toolpaths for CNC/laser fabrication and [[FigCraft-UI-Systems]].
#vector #toolpaths
""",
            ),
            (
                "CadCraft-3D-Blockout",
                """---
title: CadCraft Parametric 3D Blockout & Mechanical Assemblies
domain: hardware-fabrication
craft_app: CadCraft
papers: [PAPER-07, PAPER-08, PAPER-09]
tags: [cadcraft, 3d-printing, step, mechanical-cad, enclosure]
---
[[CadCraft-3D-Blockout]] bridges [[Architectural-Design-Thinking]] and [[PCB-Fabrication-Pipeline]] by synthesizing parametric mechanical enclosures, camera perspective rigs for [[Graphic-Engineering-Loop]], and structural tolerances.
#cad #3d-fabrication
""",
            ),
            (
                "PCB-Fabrication-Pipeline",
                """---
title: Custom IoT PCB Design & Hardware Fabrication Pipeline
domain: hardware-fabrication
craft_app: CadCraft
papers: [PAPER-10, PAPER-11, PAPER-12, PAPER-13]
tags: [pcb, gerber, kicad, iot-hardware, smt-assembly, fabrication]
---
The [[PCB-Fabrication-Pipeline]] transforms schematic capture, multilayer impedance routing, and BOM validation into manufacturable Gerber/ODB++ outputs.
Directly interfaces with [[CadCraft-3D-Blockout]] for electromechanical enclosures, [[VectorCraft-Precision-Paths]] for silkscreen/trace geometry, and [[Quantum-Orch-OR-Consciousness]] sensor arrays.
#hardware #pcb-layout #dfm
""",
            ),
            (
                "Architectural-Design-Thinking",
                """---
title: Architectural Design Thinking & Spatial Tectonics PDF Corpus
domain: architecture
craft_app: DesignCraft
papers: [PAPER-14, PAPER-15, PAPER-16, PAPER-17, PAPER-18]
tags: [architecture, design-thinking, tectonics, pdf-corpus, spatial-synthesis]
---
[[Architectural-Design-Thinking]] synthesizes 200+ architectural monographs and PDFs via [[PdfCraft-Document-Intelligence]] and [[CadCraft-3D-Blockout]].
Applies double-diamond product discovery, spatial hierarchy, and structural load paths into [[Graphic-Engineering-Loop]] and [[DeckCraft-Executive-Pitch]].
#architecture-pdfs #spatial-design
""",
            ),
            (
                "Quantum-Orch-OR-Consciousness",
                """---
title: Quantum Orch-OR Microtubule Coherence & Computational Frameworks
domain: quantum-computation
craft_app: GridCraft
papers: [PAPER-19, PAPER-20, PAPER-21, PAPER-22]
tags: [quantum, orch-or, penrose-hameroff, microtubules, non-computable-synthesis]
---
[[Quantum-Orch-OR-Consciousness]] models Objective Reduction in Dipolar Microtubule Lattices, connecting biophysical resonance models in [[GridCraft-Simulation-Matrix]] with acoustic harmonics in [[SoundCraft-DSP-Engine]] and hardware telemetry in [[PCB-Fabrication-Pipeline]].
#orch-or #quantum-cognition
""",
            ),
            (
                "PhotoCraft-Compositor",
                """---
title: PhotoCraft Layer Stack & Dirty-Gradient Raster Synthesis
domain: artcraft-suite
craft_app: PhotoCraft
papers: [PAPER-23, PAPER-24]
tags: [photocraft, raster, compositing, dirty-gradient]
---
[[PhotoCraft-Compositor]] executes multi-pass raster texturing, halftones, and dirty-gradient color blends for [[Graphic-Engineering-Loop]] and [[LightCraft-Color-Grading]].
""",
            ),
            (
                "LightCraft-Color-Grading",
                """---
title: LightCraft Spectral RAW Development & Look-Up Tables
domain: artcraft-suite
craft_app: LightCraft
papers: [PAPER-25, PAPER-26]
tags: [lightcraft, color-grading, raw-pipeline, aces]
---
[[LightCraft-Color-Grading]] manages ACES color spaces and filmic tone curves between [[PhotoCraft-Compositor]] and [[FilmCraft-NonLinear-Timeline]].
""",
            ),
            (
                "DesignCraft-Layout-System",
                """---
title: DesignCraft Swiss Grid & Print Publication Typography
domain: artcraft-suite
craft_app: DesignCraft
papers: [PAPER-27, PAPER-28]
tags: [designcraft, typography, print-production, indesign-parity]
---
[[DesignCraft-Layout-System]] compiles multi-page editorial layouts from [[Architectural-Design-Thinking]], [[WordCraft-Editorial-Manuscript]], and [[PdfCraft-Document-Intelligence]].
""",
            ),
            (
                "FilmCraft-NonLinear-Timeline",
                """---
title: FilmCraft Non-Linear Cinema Assembly & EDL Pipeline
domain: artcraft-suite
craft_app: FilmCraft
papers: [PAPER-29, PAPER-30]
tags: [filmcraft, nle, video-editing, cinema-pipeline]
---
[[FilmCraft-NonLinear-Timeline]] sequences animatics and final renders from [[EffectCraft-Motion-Compositing]], [[SoundCraft-DSP-Engine]], and [[ScriptCraft-Narrative-Engine]].
""",
            ),
            (
                "EffectCraft-Motion-Compositing",
                """---
title: EffectCraft Node/Layer Motion Graphics & VFX Shaders
domain: artcraft-suite
craft_app: EffectCraft
papers: [PAPER-31]
tags: [effectcraft, vfx, keyframes, motion-graphics]
---
[[EffectCraft-Motion-Compositing]] drives procedural particle systems and camera projections linked to [[FilmCraft-NonLinear-Timeline]] and [[Graphic-Engineering-Loop]].
""",
            ),
            (
                "SoundCraft-DSP-Engine",
                """---
title: SoundCraft DAW Session, Stem Mastering & Acoustic DSP
domain: artcraft-suite
craft_app: SoundCraft
papers: [PAPER-32]
tags: [soundcraft, daw, dsp, audio-synthesis]
---
[[SoundCraft-DSP-Engine]] synthesizes spatial audio stems and harmonic resonance profiles linked to [[FilmCraft-NonLinear-Timeline]] and [[Quantum-Orch-OR-Consciousness]].
""",
            ),
            (
                "FigCraft-UI-Systems",
                """---
title: FigCraft Component Tokens & Interactive Interface Design
domain: artcraft-suite
craft_app: FigCraft
papers: [PAPER-33]
tags: [figcraft, design-tokens, ui-ux, interactive-prototyping]
---
[[FigCraft-UI-Systems]] translates [[Architectural-Design-Thinking]] and [[VectorCraft-Precision-Paths]] into responsive interface component hierarchies.
""",
            ),
            (
                "DeckCraft-Executive-Pitch",
                """---
title: DeckCraft Visual Storytelling & Architecture Presentation
domain: artcraft-suite
craft_app: DeckCraft
papers: [PAPER-34]
tags: [deckcraft, presentations, slide-systems]
---
[[DeckCraft-Executive-Pitch]] distills complex graphs from [[GridCraft-Simulation-Matrix]] and [[Architectural-Design-Thinking]] into executive slide narratives.
""",
            ),
            (
                "GridCraft-Simulation-Matrix",
                """---
title: GridCraft Quantitative Financial & Tensor Modeling
domain: artcraft-suite
craft_app: GridCraft
papers: [PAPER-35]
tags: [gridcraft, spreadsheets, simulation, quantitative-modeling]
---
[[GridCraft-Simulation-Matrix]] computes unit economics ($0.05 query printing prices), BOM cost matrices for [[PCB-Fabrication-Pipeline]], and tensor states for [[Quantum-Orch-OR-Consciousness]].
""",
            ),
            (
                "WordCraft-Editorial-Manuscript",
                """---
title: WordCraft Structured Long-Form Technical & Academic Authoring
domain: artcraft-suite
craft_app: WordCraft
papers: [PAPER-36]
tags: [wordcraft, academic-writing, lexicographical-taxonomy]
---
[[WordCraft-Editorial-Manuscript]] maintains the lexicographical taxonomy across all 36 research papers and feeds [[DesignCraft-Layout-System]] and [[PdfCraft-Document-Intelligence]].
""",
            ),
            (
                "PdfCraft-Document-Intelligence",
                """---
title: PdfCraft OCR, Redaction & Preflight Archival Engine
domain: artcraft-suite
craft_app: PdfCraft
papers: [PAPER-14, PAPER-36]
tags: [pdfcraft, pdf-a, ocr, document-graph]
---
[[PdfCraft-Document-Intelligence]] extracts structured vector/text graphs from 200+ architecture PDFs and links them into [[Architectural-Design-Thinking]] and [[WordCraft-Editorial-Manuscript]].
""",
            ),
            (
                "ScriptCraft-Narrative-Engine",
                """---
title: ScriptCraft Fountain Screenplay & Cinematic Prompt Language
domain: artcraft-suite
craft_app: ScriptCraft
papers: [PAPER-01, PAPER-29]
tags: [scriptcraft, fountain, cinematic-prompt-language, storyboards]
---
[[ScriptCraft-Narrative-Engine]] structures scene breakdowns and camera lens telemetry for [[Graphic-Engineering-Loop]] and [[FilmCraft-NonLinear-Timeline]].
""",
            ),
        ]

        for note_id, raw_md in seed_notes:
            self.add_markdown_note(note_id=note_id, raw_markdown=raw_md)

        return self

    @classmethod
    def from_seed_vault(cls) -> "ObsidianVaultIndexer":
        """Create and return an ObsidianVaultIndexer pre-loaded with the multi-disciplinary seed vault."""
        indexer = cls()
        return indexer.load_seed_vault()
