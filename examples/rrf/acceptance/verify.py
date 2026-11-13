"""Controller-owned acceptance checks. Never mounted writable into generated-code runner."""
import json
import math
import unittest
from fusion import fuse, scores
from search_app import search_results


class Acceptance(unittest.TestCase):
    def test_hand_calculated_scores(self):
        actual = scores([["a", "b"], ["b", "c", "a"]])
        self.assertAlmostEqual(actual["a"], 1/61 + 1/63, places=12)
        self.assertAlmostEqual(actual["b"], 1/62 + 1/61, places=12)
        self.assertAlmostEqual(actual["c"], 1/62, places=12)
        self.assertEqual(fuse([["a", "b"], ["b", "c", "a"]]), ["b", "a", "c"])

    def test_default_and_custom_k(self):
        self.assertAlmostEqual(scores([["x"]])["x"], 1/61, places=12)
        self.assertAlmostEqual(scores([["x"]], k=2)["x"], 1/3, places=12)

    def test_empty(self):
        self.assertEqual(fuse([]), [])
        self.assertEqual(scores([[], []]), {})

    def test_ties(self):
        self.assertEqual(fuse([["b", "a"], ["a", "b"]]), ["a", "b"])

    def test_duplicates_preserve_original_positions(self):
        values = scores([["a", "a", "b"]])
        self.assertAlmostEqual(values["a"], 1/61)
        self.assertAlmostEqual(values["b"], 1/63)

    def test_limits(self):
        self.assertEqual(fuse([["a", "b"]], limit=1), ["a"])
        self.assertEqual(fuse([["a"]], limit=0), [])
        for limit in (-1, 1.5, True):
            with self.assertRaises(ValueError):
                fuse([["a"]], limit=limit)

    def test_invalid_k(self):
        for k in (0, -1, True, float("nan"), float("inf"), "60"):
            with self.assertRaises(ValueError):
                scores([["a"]], k=k)

    def test_existing_caller(self):
        result = search_results(["a", "b"], ["b", "a"], limit=1)
        self.assertEqual(result, {"documents": ["a"], "method": "fusion"})


def ndcg(ids, relevance, cutoff=3):
    def dcg(items):
        return sum((2**relevance.get(doc, 0)-1)/math.log2(i+2) for i, doc in enumerate(items[:cutoff]))
    ideal = dcg(sorted(relevance, key=relevance.get, reverse=True))
    return dcg(ids)/ideal if ideal else 0.0


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Acceptance)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    queries = [
        {"rankings": [["a", "b", "c"], ["b", "c", "a"]], "qrels": {"a": 1, "b": 3, "c": 2}},
        {"rankings": [["d", "e", "f"], ["f", "e", "d"]], "qrels": {"d": 3, "e": 2, "f": 1}},
        {"rankings": [["g", "h", "i"], ["h", "g", "i"]], "qrels": {"g": 2, "h": 3, "i": 0}},
        {"rankings": [["j", "k", "l"], ["l", "k", "j"]], "qrels": {"j": 0, "k": 3, "l": 2}}
    ]
    if result.wasSuccessful():
        measurements = [{"query": i, "first_retriever_ndcg3": ndcg(q["rankings"][0], q["qrels"]),
                         "rrf_ndcg3": ndcg(fuse(q["rankings"]), q["qrels"])} for i, q in enumerate(queries)]
        print("METRICS_JSON=" + json.dumps({"dataset": "four synthetic queries; no statistical claim",
              "paper_benchmark_reproduced": False, "tests": result.testsRun, "queries": measurements}))
    raise SystemExit(0 if result.wasSuccessful() else 1)
