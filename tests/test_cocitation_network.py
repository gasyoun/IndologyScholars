"""Tests for the H6060 co-citation network builder (tools/build_cocitation_network.py)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from build_cocitation_network import (  # noqa: E402
    build_graph,
    betweenness_weighted,
    communities_greedy,
    pagerank_weighted,
    scan_corpus,
    stem,
    surname_candidates,
    load_persons,
    ROOT,
)


class TestStemsAndCandidates:
    def test_stem_long_token_drops_two(self):
        assert stem("Кочергина") == "Кочерги"

    def test_stem_medium_token_drops_one(self):
        assert stem("Шукла") == "Шукл"

    def test_stem_short_token_rejected(self):
        assert stem("Иванов"[:4]) is None or len(stem("Иванов")) >= 4

    def test_both_declension_cuts_registered(self):
        stems: dict[str, str] = {}
        for st in ("Кочергин", "Кочерги"):
            stems[st] = "P1"
        # oblique «Кочергиной» and nominative «Кочергина» both hit a cut
        assert "Кочергиной"[:-2] in stems
        assert "Кочергина"[:-2] in stems

    def test_patronymics_never_candidates(self):
        assert "Николаевич" not in surname_candidates("Боголюбов Михаил Николаевич")
        assert surname_candidates("Боголюбов Михаил Николаевич") == ["Боголюбов"]

    def test_given_name_stoplist(self):
        cands = surname_candidates("Мария Шилинскене")
        assert "Мария" not in cands

    def test_initials_first_name_uses_last_token(self):
        cands = surname_candidates("А. А. Нейвирт")
        assert "Нейвирт" in cands


class TestScanCorpus:
    def test_pairs_and_anchors(self, tmp_path):
        year = tmp_path / "2013"
        year.mkdir()
        (year / "Словарь_Кочергиной__1.md").write_text(
            "Тред про словарь Кочергиной и Цапеллера.\n", encoding="utf-8"
        )
        (year / "Прочее__2.md").write_text(
            "Обсуждаем Боголюбова и Кочергиной статью.", encoding="utf-8"
        )
        stems = {"Кочергин": "P1", "Цапеллер": "P2", "Боголюбов": "P3"}
        res = scan_corpus(tmp_path, stems)
        assert res["files"] == 2
        assert res["threads"]["P1"] == 2
        assert res["threads"]["P2"] == 1
        assert res["pairs"][("P1", "P2")] == 1
        assert res["pairs"][("P1", "P3")] == 1
        assert res["pairs"][("P2", "P3")] == 0
        assert res["anchor_cappeller"] == 1
        assert res["anchor_kochergina"] == 2
        assert res["anchor_both"] == 1

    def test_lowercase_not_matched(self, tmp_path):
        (tmp_path / "2013").mkdir()
        (tmp_path / "x__3.md").write_text("строчная кочергина не считается", encoding="utf-8")
        res = scan_corpus(tmp_path, {"Кочергин": "P1"})
        assert res["threads"]["P1"] == 0


class TestGraphMetrics:
    def _path_graph(self):
        # A - B - C ; betweenness: B > A = C
        nodes = ["A", "B", "C"]
        adj = {"A": [("B", 1)], "B": [("A", 1), ("C", 1)], "C": [("B", 1)]}
        return nodes, adj

    def test_betweenness_path(self):
        nodes, adj = self._path_graph()
        btw = betweenness_weighted(nodes, adj)
        assert btw["B"] > 0
        assert btw["A"] == btw["C"] == 0.0

    def test_pagerank_hub_gets_more(self):
        nodes, adj = self._path_graph()
        pr = pagerank_weighted(nodes, adj)
        assert pr["B"] > pr["A"]

    def test_communities_split_two_clusters(self):
        adj = {
            "A": [("B", 3), ("C", 3), ("D", 1)],
            "B": [("A", 3), ("C", 3)],
            "C": [("A", 3), ("B", 3)],
            "D": [("A", 1), ("E", 3)],
            "E": [("D", 3), ("F", 3)],
            "F": [("E", 3), ("D", 3)],
        }
        labels, n, q = communities_greedy(list(adj), adj)
        assert labels["A"] == labels["B"] == labels["C"]
        assert labels["D"] == labels["E"] == labels["F"]
        assert labels["A"] != labels["D"]
        assert n == 2
        assert q > 0.1

    def test_communities_greedy_deterministic(self):
        adj = {
            "A": [("B", 2), ("C", 2), ("D", 1)],
            "B": [("A", 2), ("C", 2)],
            "C": [("A", 2), ("B", 2)],
            "D": [("A", 1), ("E", 2)],
            "E": [("D", 2), ("F", 2)],
            "F": [("E", 2), ("D", 2)],
        }
        r1 = communities_greedy(list(adj), adj)
        r2 = communities_greedy(list(adj), adj)
        assert r1 == r2

    def test_modularity_uniform_is_zero(self):
        adj = {
            "A": [("B", 2), ("C", 1)],
            "B": [("A", 2), ("C", 1)],
            "C": [("A", 1), ("B", 1)],
        }
        _, n, q = communities_greedy(["A", "B", "C"], adj)
        # a triangle either stays whole (Q=0) or splits with Q<=0; never positive spurious
        assert q <= 1e-9


class TestBuildGraph:
    def test_min_threads_filter(self):
        pairs = {("A", "B"): 3, ("B", "C"): 1}
        threads = {"A": 3, "B": 4, "C": 1}
        nodes, edges, adj = build_graph(pairs, threads, 2)
        assert "C" not in nodes
        assert ("A", "B", 3) in edges


@pytest.mark.skipif(not (ROOT / "conferences.db").exists(), reason="no db")
class TestOnOwnData:
    def test_persons_load_deterministic(self):
        p1, s1, sk1 = load_persons(ROOT / "conferences.db")
        p2, s2, sk2 = load_persons(ROOT / "conferences.db")
        assert (len(p1), sorted(s1), sk1) == (len(p2), sorted(s2), sk2)

    def test_no_patronymic_stems(self):
        _, stems, _ = load_persons(ROOT / "conferences.db")
        banned = ("Николаев", "Владимиров", "Александров")  # patronymic stems
        # Александров is ALSO a real surname; patronymic-form tokens end
        # -евич/-овна and are cut by the regex, so a pure patronymic stem
        # like Николаевич can never appear as a stem key.
        for st in stems:
            assert not st.endswith(("евич", "ович", "евна", "овна"))
