"""H1893: versioned codebook contracts for the five-lens schema.

Covers the six controlled-vocabulary shells (native_topic, shared_topic,
community_function, renou_state, renou_register, argument_level): column
contract, explicit versions, no dangling parent_label_id, and that
renou_state/renou_register reuse the vocabulary already defined in
generate_renou_layer.py's RULE_ROWS rather than inventing conflicting names.
"""
from __future__ import annotations

from community_lenses import taxonomy
from generate_renou_layer import RULE_ROWS


def test_every_codebook_has_a_file_and_validates_clean():
    for name in taxonomy.CODEBOOK_NAMES:
        errors = taxonomy.validate_codebook(name)
        assert errors == [], f"{name}: {errors}"


def test_every_codebook_declares_one_explicit_version():
    for name in taxonomy.CODEBOOK_NAMES:
        version = taxonomy.codebook_version(name)
        assert version and version != "0.0.0", f"{name} has no explicit version"


def _copy_real_codebooks_then_override(tmp_path, monkeypatch, overrides: dict[str, str]):
    """Mirror every real codebook into tmp_path (so cross-codebook parent
    lookups still resolve), then overwrite the named ones with bad content."""
    for name in taxonomy.CODEBOOK_NAMES:
        (tmp_path / f"{name}.csv").write_text(
            taxonomy.codebook_path(name).read_text(encoding="utf-8"), encoding="utf-8"
        )
    for name, content in overrides.items():
        (tmp_path / f"{name}.csv").write_text(content, encoding="utf-8")
    monkeypatch.setattr(taxonomy, "CODEBOOKS_DIR", tmp_path)


def test_codebook_rejects_wrong_columns(tmp_path, monkeypatch):
    _copy_real_codebooks_then_override(
        tmp_path, monkeypatch, {"shared_topic": "label_id,label\nfoo,Foo\n"}
    )
    errors = taxonomy.validate_codebook("shared_topic")
    assert errors, "a codebook file with the wrong column contract must fail validation"


def test_codebook_rejects_duplicate_label_id(tmp_path, monkeypatch):
    header = ",".join(taxonomy.REQUIRED_COLUMNS)
    row = "dup,Dup,def,inc,exc,ex,,active,1.0.0"
    _copy_real_codebooks_then_override(
        tmp_path, monkeypatch, {"shared_topic": f"{header}\n{row}\n{row}\n"}
    )
    errors = taxonomy.validate_codebook("shared_topic")
    assert any("duplicate label_id" in e for e in errors)


def test_codebook_rejects_dangling_parent(tmp_path, monkeypatch):
    header = ",".join(taxonomy.REQUIRED_COLUMNS)
    row = "child,Child,def,inc,exc,ex,does_not_exist_anywhere,active,1.0.0"
    _copy_real_codebooks_then_override(
        tmp_path, monkeypatch, {"shared_topic": f"{header}\n{row}\n"}
    )
    errors = taxonomy.validate_codebook("shared_topic")
    assert any("dangling parent_label_id" in e for e in errors)


def test_codebook_rejects_unknown_status(tmp_path, monkeypatch):
    header = ",".join(taxonomy.REQUIRED_COLUMNS)
    row = "x,X,def,inc,exc,ex,,not_a_status,1.0.0"
    _copy_real_codebooks_then_override(
        tmp_path, monkeypatch, {"shared_topic": f"{header}\n{row}\n"}
    )
    errors = taxonomy.validate_codebook("shared_topic")
    assert any("unknown status" in e for e in errors)


def test_renou_state_reuses_generate_renou_layer_labels():
    state_rows = taxonomy.load_codebook("renou_state")
    state_labels = {row["label_id"]: row["label"] for row in state_rows}
    reference = {
        row["code"]: row["label"] for row in RULE_ROWS if isinstance(row, dict) and row["axis"] == "state"
    }
    for code, label in reference.items():
        assert state_labels.get(code) == label, (
            f"renou_state codebook label for {code!r} ({state_labels.get(code)!r}) "
            f"must match generate_renou_layer.py's RULE_ROWS ({label!r})"
        )


def test_renou_register_reuses_generate_renou_layer_labels():
    register_rows = taxonomy.load_codebook("renou_register")
    register_labels = {row["label_id"]: row["label"] for row in register_rows}
    reference = {
        row[1]: row[2]
        for row in RULE_ROWS
        if isinstance(row, tuple) and row[0] == "register"
    }
    for code, label in reference.items():
        assert register_labels.get(code) == label, (
            f"renou_register codebook label for {code!r} ({register_labels.get(code)!r}) "
            f"must match generate_renou_layer.py's RULE_ROWS ({label!r})"
        )


def test_argument_level_matches_data_dictionary_1_to_3_scale():
    rows = {row["label_id"] for row in taxonomy.load_codebook("argument_level")}
    # data_dictionary.md documents argument_level as an integer 1-3 scale;
    # the codebook may use either bare integers or the G1/G2/G3 house
    # nomenclature already used across the corpus (H1376/H674 notes), but it
    # must cover exactly three substantive levels plus unknown/not-applicable.
    substantive = {r for r in rows if r not in {"unknown", "not_applicable"}}
    assert len(substantive) == 3, f"expected 3 substantive argument levels, got {rows}"
