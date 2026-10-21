"""Atomic Multi-Note Trajectory Importer, Deterministic Redactor, and Brain Batch Scanner for vault-graphrag-paywall."""

from __future__ import annotations

import glob
import hashlib
import json
import os
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .vault_indexer import ARTCRAFT_APPS, ObsidianVaultIndexer, VaultNote


# Regex patterns for Deterministic Redaction + Path Normalization
SECRET_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"sk-[A-Za-z0-9\-_]{20,}"), "[REDACTED_API_KEY]"),
    (re.compile(r"AIza[0-9A-Za-z\-_]{30,}"), "[REDACTED_GOOGLE_KEY]"),
    (re.compile(r"xox[baprs]-[0-9A-Za-z\-]{10,}"), "[REDACTED_SLACK_TOKEN]"),
    (
        re.compile(r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*['\"][^'\"]{8,}['\"]"),
        r"\1: '[REDACTED_SECRET]'",
    ),
]

USER_HOME_RE = re.compile(r"/Users/[a-zA-Z0-9._\-]+")

KNOWN_SKILLS_AND_REPOS: List[str] = [
    "vault-graphrag-paywall",
    "multi-domain-lexicon",
    "tmux-agent-fleet",
    "background-agent-orchestration",
    "edge-agent-creative-pipeline",
    "research-ecosystem",
    "remote-control-skill",
    "gemini-activity-harvester",
    "parallel-worktree-isolation",
    "share-trajectory",
]


@dataclass
class ImportedTrajectoryGraph:
    """Result of importing a conversation trajectory as an Atomic Multi-Note Graph."""

    conversation_id: str
    short_id: str
    provenance_sha256: str
    parent_note_id: str
    child_note_ids: List[str] = field(default_factory=list)
    detected_papers: List[str] = field(default_factory=list)
    detected_craft_apps: List[str] = field(default_factory=list)
    detected_skills: List[str] = field(default_factory=list)
    steps_processed: int = 0
    written_files: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class TrajectorySanitizer:
    """Applies deterministic secret redaction, path normalization (/Users/... -> ~/...), and SHA-256 provenance hashing."""

    @staticmethod
    def sanitize_text(text: str) -> str:
        if not text:
            return ""
        cleaned = USER_HOME_RE.sub("~", text)
        for pattern, replacement in SECRET_PATTERNS:
            cleaned = pattern.sub(replacement, cleaned)
        return cleaned

    @classmethod
    def sanitize_records(cls, records: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], str]:
        """Return sanitized trajectory records and their deterministic SHA-256 provenance digest."""
        sanitized: List[Dict[str, Any]] = []
        hasher = hashlib.sha256()

        for rec in records:
            clean_rec = dict(rec)
            if "content" in clean_rec and isinstance(clean_rec["content"], str):
                clean_rec["content"] = cls.sanitize_text(clean_rec["content"])
            if "thinking" in clean_rec and isinstance(clean_rec["thinking"], str):
                clean_rec["thinking"] = cls.sanitize_text(clean_rec["thinking"])
            if "tool_calls" in clean_rec and isinstance(clean_rec["tool_calls"], list):
                cleaned_calls = []
                for tc in clean_rec["tool_calls"]:
                    tc_copy = dict(tc)
                    if "args" in tc_copy:
                        raw_args = json.dumps(tc_copy["args"], sort_keys=True)
                        sanitized_args_str = cls.sanitize_text(raw_args)
                        try:
                            tc_copy["args"] = json.loads(sanitized_args_str)
                        except Exception:
                            tc_copy["args"] = sanitized_args_str
                    cleaned_calls.append(tc_copy)
                clean_rec["tool_calls"] = cleaned_calls

            canonical_line = json.dumps(
                {
                    "step_index": clean_rec.get("step_index"),
                    "source": clean_rec.get("source"),
                    "type": clean_rec.get("type"),
                    "content": clean_rec.get("content", ""),
                    "tool_calls": clean_rec.get("tool_calls", []),
                },
                sort_keys=True,
            )
            hasher.update(canonical_line.encode("utf-8"))
            sanitized.append(clean_rec)

        return sanitized, hasher.hexdigest()


class AtomicTrajectoryGraphImporter:
    """Converts agent conversation transcripts into an Atomic Multi-Note Graph inside ObsidianVaultIndexer."""

    def __init__(self, indexer: Optional[ObsidianVaultIndexer] = None) -> None:
        self.indexer = indexer if indexer is not None else ObsidianVaultIndexer.from_seed_vault()

    @staticmethod
    def resolve_transcript_path(
        conversation_id_or_path: str,
        brain_root: Optional[str] = None,
    ) -> Tuple[str, str]:
        """Resolve a conversation://<id>, UUID, or file path to (conversation_id, transcript_path)."""
        target = conversation_id_or_path.strip()
        if target.startswith("conversation://"):
            target = target.replace("conversation://", "").strip("/")

        if os.path.isfile(target):
            conv_id = Path(target).parent.parent.parent.name
            if target.endswith("transcript.jsonl"):
                full_p = target.replace("transcript.jsonl", "transcript_full.jsonl")
                if os.path.isfile(full_p):
                    target = full_p
            return conv_id, target

        root = brain_root or os.path.expanduser("~/.gemini/antigravity-cli/brain")
        conv_dir = os.path.join(root, target, ".system_generated", "logs")
        full_cand = os.path.join(conv_dir, "transcript_full.jsonl")
        compact_cand = os.path.join(conv_dir, "transcript.jsonl")
        if os.path.isfile(full_cand):
            return target, full_cand
        if os.path.isfile(compact_cand):
            return target, compact_cand

        raise FileNotFoundError(
            f"Could not find transcript for '{conversation_id_or_path}' in {root}"
        )

    @staticmethod
    def load_jsonl(path: str) -> List[Dict[str, Any]]:
        records: List[Dict[str, Any]] = []
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except Exception:
                    continue
        return records

    @staticmethod
    def detect_entities(full_corpus_text: str) -> Tuple[List[str], List[str], List[str]]:
        """Auto-detect [[PAPER-XX]], [[ArtCraft]], and #skill entities mentioned in the trajectory."""
        detected_papers: List[str] = []
        for m in re.finditer(r"(?i)\bpaper[\s_\-]*0*([1-9]|[12][0-9]|3[0-6])\b", full_corpus_text):
            num = int(m.group(1))
            code = f"PAPER-{num:02d}"
            if code not in detected_papers:
                detected_papers.append(code)

        if "36 research paper" in full_corpus_text.lower() or "pillar1_edge" in full_corpus_text.lower():
            for num in (1, 2, 13, 15, 25, 26, 36):
                code = f"PAPER-{num:02d}"
                if code not in detected_papers:
                    detected_papers.append(code)

        detected_apps: List[str] = []
        lower_text = full_corpus_text.lower()
        for app in ARTCRAFT_APPS:
            if app.lower() in lower_text and app not in detected_apps:
                detected_apps.append(app)

        detected_skills: List[str] = []
        for sk in KNOWN_SKILLS_AND_REPOS:
            if sk.lower() in lower_text and sk not in detected_skills:
                detected_skills.append(sk)

        return sorted(detected_papers), detected_apps, detected_skills

    def import_trajectory(
        self,
        conversation_id_or_path: str,
        vault_dir: Optional[str] = None,
        brain_root: Optional[str] = None,
        max_milestones: int = 8,
    ) -> ImportedTrajectoryGraph:
        """Import a single conversation trajectory as an Atomic Multi-Note Graph (1 parent summary note + N milestone child notes)."""
        conv_id, transcript_path = self.resolve_transcript_path(
            conversation_id_or_path, brain_root=brain_root
        )
        raw_records = self.load_jsonl(transcript_path)
        sanitized_records, provenance_sha256 = TrajectorySanitizer.sanitize_records(raw_records)

        short_id = conv_id.split("-")[0] if "-" in conv_id else conv_id[:8]
        parent_note_id = f"Trajectory-{short_id}"

        full_text_chunks: List[str] = []
        user_prompts: List[str] = []
        assistant_summaries: List[str] = []
        milestone_groups: List[Dict[str, Any]] = []

        current_tools: List[Dict[str, Any]] = []
        current_response: str = ""
        current_step_range: List[int] = []

        for rec in sanitized_records:
            idx = rec.get("step_index", 0)
            stype = rec.get("type", "")
            source = rec.get("source", "")
            content = rec.get("content", "") or ""
            tool_calls = rec.get("tool_calls", []) or []

            full_text_chunks.append(content)
            for tc in tool_calls:
                full_text_chunks.append(json.dumps(tc))

            if stype == "USER_INPUT" or source in ("USER_EXPLICIT", "user"):
                if content.strip():
                    user_prompts.append(content.strip())
            elif stype == "PLANNER_RESPONSE" or source in ("MODEL", "assistant"):
                if content.strip():
                    assistant_summaries.append(content.strip())
                    current_response = content.strip()
                if tool_calls:
                    current_tools.extend(tool_calls)
                    current_step_range.append(idx)
                    if len(current_tools) >= 4:
                        milestone_groups.append(
                            {
                                "steps": list(current_step_range),
                                "tools": list(current_tools),
                                "summary": current_response,
                            }
                        )
                        current_tools.clear()
                        current_step_range.clear()
                        current_response = ""

        if current_tools or (not milestone_groups and assistant_summaries):
            milestone_groups.append(
                {
                    "steps": current_step_range or [0],
                    "tools": list(current_tools),
                    "summary": current_response or (assistant_summaries[-1] if assistant_summaries else "Final synthesis"),
                }
            )

        milestone_groups = milestone_groups[:max_milestones]
        all_text = "\n".join(full_text_chunks)
        detected_papers, detected_apps, detected_skills = self.detect_entities(all_text)

        child_note_ids: List[str] = []
        written_files: List[str] = []

        if vault_dir:
            os.makedirs(os.path.join(vault_dir, "trajectories"), exist_ok=True)

        # 1. Create Atomic Child Milestone Notes
        for m_idx, m_group in enumerate(milestone_groups, start=1):
            child_id = f"{parent_note_id}-Milestone-{m_idx:02d}"
            child_note_ids.append(child_id)

            tool_names = [tc.get("name", "tool") for tc in m_group["tools"]]
            tool_lines = []
            for tc in m_group["tools"][:6]:
                t_name = tc.get("name", "tool")
                t_args = tc.get("args", {})
                if isinstance(t_args, dict):
                    path_arg = t_args.get("Path") or t_args.get("CommandLine") or t_args.get("toolSummary") or ""
                    tool_lines.append(f"- `{t_name}`: `{str(path_arg)[:120]}`")
                else:
                    tool_lines.append(f"- `{t_name}`")

            group_text = json.dumps(m_group)
            m_papers, m_apps, m_skills = self.detect_entities(group_text)
            effective_papers = m_papers or detected_papers[:3]
            effective_apps = m_apps or detected_apps[:2]

            wikilink_refs = [f"[[{parent_note_id}]]"]
            wikilink_refs.extend(f"[[{p}]]" for p in effective_papers)
            wikilink_refs.extend(f"[[{a}]]" for a in effective_apps)
            wikilink_refs.append("[[Graphic Engineering Loop]]")

            tag_refs = ["#trajectory", "#milestone"] + [f"#{s}" for s in (m_skills or detected_skills[:3])]

            child_md = (
                f"---\n"
                f"title: {child_id}\n"
                f"domain: agent_trajectory_milestone\n"
                f"conversation_id: {conv_id}\n"
                f"provenance_sha256: {provenance_sha256}\n"
                f"papers: [{', '.join(effective_papers)}]\n"
                f"craft_app: {effective_apps[0] if effective_apps else 'VectorCraft'}\n"
                f"---\n"
                f"# {child_id}: Execution Milestone #{m_idx}\n\n"
                f"**Parent Trajectory**: [[{parent_note_id}]]\n"
                f"**Connected Entities**: {' '.join(wikilink_refs)}\n"
                f"**Tags**: {' '.join(tag_refs)}\n\n"
                f"## Tool Invocations ({len(tool_names)})\n"
                + ("\n".join(tool_lines) if tool_lines else "- Reasoning & synthesis checkpoint")
                + "\n\n## Milestone Deliverable Summary\n"
                + (m_group["summary"][:600] if m_group["summary"] else "Executed atomic build/verification steps.")
                + "\n"
            )

            child_path = None
            if vault_dir:
                child_path = os.path.join(vault_dir, "trajectories", f"{child_id}.md")
                with open(child_path, "w", encoding="utf-8") as f:
                    f.write(child_md)
                written_files.append(child_path)

            child_note = ObsidianVaultIndexer.parse_markdown(child_id, child_md, path=child_path)
            self.indexer.add_note(child_note)

        # 2. Create Parent Trajectory Summary Note linking to all Child Milestones, Papers, Craft Apps, and Skills
        parent_wikilinks = [f"[[{cid}]]" for cid in child_note_ids]
        parent_wikilinks.extend(f"[[{p}]]" for p in detected_papers)
        parent_wikilinks.extend(f"[[{a}]]" for a in detected_apps)
        parent_wikilinks.extend(["[[Graphic Engineering Loop]]", "[[36 Research Papers Corpus]]"])

        parent_tags = ["#trajectory", "#procedural-memory", "#one-shot-build"] + [
            f"#{s}" for s in detected_skills
        ]

        objective_preview = user_prompts[0][:500] if user_prompts else "Autonomous subagent execution trajectory"
        final_summary_preview = (
            assistant_summaries[-1][:800]
            if assistant_summaries
            else "Completed multi-step implementation and verification."
        )

        parent_md = (
            f"---\n"
            f"title: {parent_note_id}\n"
            f"domain: agent_trajectory\n"
            f"conversation_id: {conv_id}\n"
            f"provenance_sha256: {provenance_sha256}\n"
            f"steps_count: {len(sanitized_records)}\n"
            f"papers: [{', '.join(detected_papers)}]\n"
            f"craft_app: {detected_apps[0] if detected_apps else 'VectorCraft'}\n"
            f"---\n"
            f"# {parent_note_id}: Autonomous Agent Execution Trajectory\n\n"
            f"- **Conversation ID**: `{conv_id}`\n"
            f"- **Provenance SHA-256**: `{provenance_sha256}`\n"
            f"- **Total Steps**: {len(sanitized_records)}\n"
            f"- **Metering Tier**: Flat `$0.05` Printing Price (`VendingMachinePaywall`)\n\n"
            f"## Initial Objective\n"
            f"{objective_preview}\n\n"
            f"## Atomic Milestone Graph Nodes ({len(child_note_ids)})\n"
            + "\n".join(f"- [[{cid}]]" for cid in child_note_ids)
            + "\n\n## Connected Knowledge Graph Links\n"
            + " ".join(parent_wikilinks)
            + "\n\n## Tags\n"
            + " ".join(parent_tags)
            + "\n\n## Final Deliverable Synthesis\n"
            + final_summary_preview
            + "\n"
        )

        parent_path = None
        if vault_dir:
            parent_path = os.path.join(vault_dir, "trajectories", f"{parent_note_id}.md")
            with open(parent_path, "w", encoding="utf-8") as f:
                f.write(parent_md)
            written_files.insert(0, parent_path)

        parent_note = ObsidianVaultIndexer.parse_markdown(parent_note_id, parent_md, path=parent_path)
        self.indexer.add_note(parent_note)

        return ImportedTrajectoryGraph(
            conversation_id=conv_id,
            short_id=short_id,
            provenance_sha256=provenance_sha256,
            parent_note_id=parent_note_id,
            child_note_ids=child_note_ids,
            detected_papers=detected_papers,
            detected_craft_apps=detected_apps,
            detected_skills=detected_skills,
            steps_processed=len(sanitized_records),
            written_files=written_files,
        )

    def import_all_recent(
        self,
        brain_root: Optional[str] = None,
        vault_dir: Optional[str] = None,
        limit: int = 10,
    ) -> List[ImportedTrajectoryGraph]:
        """Batch-scan ~/.gemini/antigravity-cli/brain/* and import recent trajectories into the Obsidian Vault GraphRAG index."""
        root = brain_root or os.path.expanduser("~/.gemini/antigravity-cli/brain")
        pattern = os.path.join(root, "*", ".system_generated", "logs", "transcript_full.jsonl")
        matches = glob.glob(pattern)
        if not matches:
            fallback_pattern = os.path.join(root, "*", ".system_generated", "logs", "transcript.jsonl")
            matches = glob.glob(fallback_pattern)

        matches.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        selected = matches[:limit]

        results: List[ImportedTrajectoryGraph] = []
        for path in selected:
            try:
                imported = self.import_trajectory(path, vault_dir=vault_dir, brain_root=root)
                results.append(imported)
            except Exception:
                continue
        return results
