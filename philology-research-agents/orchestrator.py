"""Philology Research Lab — multi-agent orchestrator (DeepSeek API).

Chains 6 agents sequentially through DeepSeek (OpenAI-compatible).
Each agent receives the shared context, its role prompt, and the prior output.

Usage:
  python orchestrator.py "Ваш вопрос по филологии..."
  python orchestrator.py --output result.md "Вопрос..."
  DEEPSEEK_API_KEY=sk-... python orchestrator.py "Вопрос..."

Configuration (via environment):
  DEEPSEEK_API_KEY  — required (https://platform.deepseek.com/api_keys)
  DEEPSEEK_MODEL    — default: deepseek-chat
"""

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AGENTS_DIR = ROOT / "agents"
SHARED_DIR = ROOT / "shared"
EDITORS_DIR = ROOT / "editors"

# DeepSeek API (OpenAI-compatible)
try:
    from openai import OpenAI
except ImportError:
    sys.exit("Install openai: pip install openai>=1.0.0")

API_KEY = os.environ.get("DEEPSEEK_API_KEY")
if not API_KEY:
    sys.exit("Set DEEPSEEK_API_KEY environment variable")

MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
TEMPERATURE = 0.0
MAX_TOKENS = 4096

client = OpenAI(api_key=API_KEY, base_url="https://api.deepseek.com/v1")

# Agent order and descriptions
AGENTS = [
    ("1-researcher.md", "Researcher / Исследователь", "Secondary literature, state of the question / Вторичная литература, обзор"),
    ("2-source-critic.md", "Source Critic / Филолог-источниковед", "Primary sources, editions, witnesses / Первоисточники, издания, свидетели"),
    ("3-verifier.md", "Verifier / Верификатор", "Reference accuracy, hallucination check / Проверка ссылок, галлюцинации"),
    ("4-analyst.md", "Critical Analyst / Критический аналитик", "Evidence quality A–E / Качество доказательств A–E"),
    ("5-synthesizer.md", "Synthesizer / Синтезатор", "Integrated verdict 1–10 / Сводный вердикт 1–10"),
    ("6-editor.md", "Editor / Редактор-оформитель", "Terminology, transliteration, References / Терминология, References"),
]


def load_md(path: str) -> str:
    """Load a .md file, stripping YAML frontmatter if present."""
    p = ROOT / path
    if not p.exists():
        return ""
    text = p.read_text(encoding="utf-8")
    # Strip YAML frontmatter (--- ... ---)
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            text = parts[2]
    return text.strip()


def build_system_prompt(agent_file: str, editor_profile: str | None = None) -> str:
    """Build the system prompt: shared context + agent role + optional editor profile."""
    parts = []

    # Shared context (applies to all agents)
    for shared_file in ["source-hierarchy.md", "evidence-scale.md", "conventions.md"]:
        content = load_md(f"shared/{shared_file}")
        if content:
            parts.append(content)

    # Editor profile (target journal style)
    if editor_profile:
        editor_path = EDITORS_DIR / editor_profile
        if editor_path.exists():
            parts.append(editor_path.read_text(encoding="utf-8"))

    # Agent-specific prompt
    agent_prompt = load_md(f"agents/{agent_file}")
    if agent_prompt:
        parts.append(agent_prompt)

    return "\n\n---\n\n".join(parts)


def run_agent(system_prompt: str, user_message: str, agent_label: str) -> str:
    """Run a single agent via DeepSeek API."""
    print(f"\n  [{agent_label}] Running...", end="", flush=True)
    try:
        response = client.chat.completions.create(
            model=MODEL,
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


def run_pipeline(question: str, editor_profile: str | None = None, output_file: str | None = None) -> str:
    """Run the full 6-agent pipeline and return the final output."""
    results = []

    print(f"Question: {question}")
    print(f"Model: {MODEL}, temperature: {TEMPERATURE}")
    print()

    user_msg = question
    for agent_file, label, _desc in AGENTS:
        system = build_system_prompt(agent_file, editor_profile)
        output = run_agent(system, user_msg, label)
        results.append(f"## {label}\n\n{output}")
        user_msg = f"Original question:\n{question}\n\nPrevious agent output:\n{output}"
        time.sleep(0.5)  # rate limit buffer

    final = "\n\n---\n\n".join(results)
    header = f"# Philology Research Lab — Pipeline Output\n\n"
    header += f"**Question:** {question}\n"
    header += f"**Model:** {MODEL} | **Temperature:** {TEMPERATURE}\n"
    header += f"**Editor profile:** {editor_profile or 'default (ППВ)'}\n\n"
    header += "---\n\n"

    full_output = header + final

    if output_file:
        Path(output_file).write_text(full_output, encoding="utf-8")
        print(f"\nOutput written to {output_file}")

    return full_output


def main():
    args = sys.argv[1:]
    output_file = None
    editor_profile = None

    # Parse arguments
    question_parts = []
    i = 0
    while i < len(args):
        if args[i] == "--output" and i + 1 < len(args):
            output_file = args[i + 1]
            i += 2
        elif args[i] == "--editor" and i + 1 < len(args):
            editor_profile = args[i + 1]
            i += 2
        else:
            question_parts.append(args[i])
            i += 1

    question = " ".join(question_parts).strip()
    if not question:
        print(__doc__)
        print("\nAvailable editor profiles:")
        if EDITORS_DIR.exists():
            for f in sorted(EDITORS_DIR.glob("*.md")):
                if f.name != "README.md":
                    print(f"  --editor {f.name}")
        sys.exit(1)

    output = run_pipeline(question, editor_profile, output_file)
    print("\n" + "=" * 60)
    print(output)


if __name__ == "__main__":
    main()
