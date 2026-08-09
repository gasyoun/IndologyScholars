"""Philology Research Lab — multi-agent orchestrator.

Chains 6 agents sequentially through an OpenAI-compatible chat API
(DeepSeek, OpenModel, or any compatible base URL) or the Anthropic Messages API.

Usage:
  python orchestrator.py "Ваш вопрос по филологии..."
  python orchestrator.py --output result.md "Вопрос..."
  python orchestrator.py --editor ppv.md "Вопрос..."
  python orchestrator.py --dry-run "Вопрос..."   # load prompts only, no API

Configuration (environment, first match wins for provider):
  ANTHROPIC_API_KEY + optional ANTHROPIC_MODEL (default claude-sonnet-4-20250514)
  OPENMODEL_API_KEY / OPENMODEL_BASE_URL / OPENMODEL_MODEL
  DEEPSEEK_API_KEY  / DEEPSEEK_MODEL (default deepseek-v4-flash)
  Or set PROVIDER=anthropic|openmodel|deepseek|openai explicitly.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AGENTS_DIR = ROOT / "agents"
SHARED_DIR = ROOT / "shared"
EDITORS_DIR = ROOT / "editors"

AGENTS = [
    ("1-researcher.md", "Researcher / Исследователь", "Secondary literature, state of the question"),
    ("2-source-critic.md", "Source Critic / Филолог-источниковед", "Primary sources, editions, witnesses"),
    ("3-verifier.md", "Verifier / Верификатор", "Reference accuracy, hallucination check"),
    ("4-analyst.md", "Critical Analyst / Критический аналитик", "Evidence quality A–E"),
    ("5-synthesizer.md", "Synthesizer / Синтезатор", "Integrated verdict 1–10"),
    ("6-editor.md", "Editor / Редактор-оформитель", "Terminology, transliteration, References"),
]

TEMPERATURE = 0.0
MAX_TOKENS = 4096


def load_md(path: str | Path) -> str:
    """Load a .md file, stripping YAML frontmatter if present."""
    p = Path(path)
    if not p.is_absolute():
        p = ROOT / p
    if not p.exists():
        return ""
    text = p.read_text(encoding="utf-8")
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            text = parts[2]
    return text.strip()


def build_system_prompt(agent_file: str, editor_profile: str | None = None) -> str:
    """Build the system prompt: shared context + agent role + optional editor profile."""
    parts = []
    for shared_file in ("source-hierarchy.md", "evidence-scale.md", "conventions.md"):
        content = load_md(f"shared/{shared_file}")
        if content:
            parts.append(content)
    if editor_profile:
        editor_path = EDITORS_DIR / editor_profile
        if editor_path.exists():
            parts.append(editor_path.read_text(encoding="utf-8"))
    agent_prompt = load_md(f"agents/{agent_file}")
    if agent_prompt:
        parts.append(agent_prompt)
    return "\n\n---\n\n".join(parts)


def resolve_provider() -> dict:
    """Pick API backend from env. Returns dict with keys provider, model, api_key, base_url."""
    forced = (os.environ.get("PROVIDER") or "").strip().lower()
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    openmodel_key = os.environ.get("OPENMODEL_API_KEY")
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")

    if forced == "anthropic" or (not forced and anthropic_key):
        return {
            "provider": "anthropic",
            "api_key": anthropic_key,
            "model": os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
            "base_url": None,
        }
    if forced == "openmodel" or (not forced and openmodel_key):
        return {
            "provider": "openai_compat",
            "api_key": openmodel_key,
            "model": os.environ.get("OPENMODEL_MODEL", "deepseek-v4-flash"),
            "base_url": os.environ.get("OPENMODEL_BASE_URL", "https://api.openmodel.ai/v1"),
        }
    if forced == "deepseek" or (not forced and deepseek_key):
        return {
            "provider": "openai_compat",
            "api_key": deepseek_key,
            "model": os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash"),
            "base_url": os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
        }
    if forced == "openai" or (not forced and openai_key):
        return {
            "provider": "openai_compat",
            "api_key": openai_key,
            "model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            "base_url": os.environ.get("OPENAI_BASE_URL"),
        }
    return {"provider": None, "api_key": None, "model": None, "base_url": None}


def run_agent(system_prompt: str, user_message: str, agent_label: str, cfg: dict | None = None) -> str:
    """Run a single agent via the resolved provider."""
    cfg = cfg or resolve_provider()
    if not cfg.get("api_key"):
        raise RuntimeError(
            "No API key set. Export ANTHROPIC_API_KEY, OPENMODEL_API_KEY, or DEEPSEEK_API_KEY."
        )
    print(f"\n  [{agent_label}] Running...", end="", flush=True)
    try:
        if cfg["provider"] == "anthropic":
            try:
                import anthropic
            except ImportError as exc:
                raise RuntimeError("Install anthropic: pip install anthropic>=0.39.0") from exc
            client = anthropic.Anthropic(api_key=cfg["api_key"])
            response = client.messages.create(
                model=cfg["model"],
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
            parts = []
            for block in response.content:
                text = getattr(block, "text", None)
                if text:
                    parts.append(text)
            output = "\n".join(parts)
        else:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise RuntimeError("Install openai: pip install openai>=1.0.0") from exc
            kwargs = {"api_key": cfg["api_key"]}
            if cfg.get("base_url"):
                kwargs["base_url"] = cfg["base_url"]
            client = OpenAI(**kwargs)
            response = client.chat.completions.create(
                model=cfg["model"],
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
            )
            output = response.choices[0].message.content or ""
        print(f" {len(output)} chars")
        return output
    except Exception as e:
        print(f" ERROR: {e}")
        return f"[ERROR] {e}"


def run_pipeline(
    question: str,
    editor_profile: str | None = None,
    output_file: str | None = None,
    dry_run: bool = False,
) -> str:
    """Run the full 6-agent pipeline and return the final output."""
    cfg = resolve_provider()
    results = []
    print(f"Question: {question}")
    if dry_run:
        print("Mode: dry-run (prompts only)")
    else:
        print(f"Provider: {cfg.get('provider')} | Model: {cfg.get('model')} | temp={TEMPERATURE}")
    print()

    user_msg = question
    for agent_file, label, _desc in AGENTS:
        system = build_system_prompt(agent_file, editor_profile)
        if dry_run:
            print(f"  [{label}] prompt {len(system)} chars")
            output = f"[dry-run] system_prompt_chars={len(system)} user_chars={len(user_msg)}"
        else:
            output = run_agent(system, user_msg, label, cfg)
        results.append(f"## {label}\n\n{output}")
        user_msg = f"Original question:\n{question}\n\nPrevious agent output:\n{output}"
        if not dry_run:
            time.sleep(0.5)

    final = "\n\n---\n\n".join(results)
    header = (
        f"# Philology Research Lab — Pipeline Output\n\n"
        f"**Question:** {question}\n"
        f"**Model:** {cfg.get('model') if not dry_run else 'dry-run'} | "
        f"**Temperature:** {TEMPERATURE}\n"
        f"**Editor profile:** {editor_profile or 'default (ППВ)'}\n\n"
        f"---\n\n"
    )
    full_output = header + final
    if output_file:
        Path(output_file).write_text(full_output, encoding="utf-8")
        print(f"\nOutput written to {output_file}")
    return full_output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question", nargs="*", help="Research question")
    parser.add_argument("--output", "-o", help="Write Markdown output to this path")
    parser.add_argument("--editor", help="Editor profile filename under editors/, e.g. ppv.md")
    parser.add_argument("--dry-run", action="store_true", help="Load prompts only; no API calls")
    args = parser.parse_args(argv)
    question = " ".join(args.question).strip()
    if not question:
        parser.print_help()
        print("\nAvailable editor profiles:")
        if EDITORS_DIR.exists():
            for f in sorted(EDITORS_DIR.glob("*.md")):
                if f.name != "README.md":
                    print(f"  --editor {f.name}")
        return 1
    output = run_pipeline(question, args.editor, args.output, dry_run=args.dry_run)
    print("\n" + "=" * 60)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
