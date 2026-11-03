import unittest

from mathesis.impasse import ImpasseDetector


class ImpasseTest(unittest.TestCase):
    def test_initial_features_zero(self):
        detector = ImpasseDetector(threshold=0.45, patience=3, window=10, budget=100)
        current = detector.features()
        self.assertEqual(current.nodes_since_progress, 0.0)
        self.assertEqual(current.duplicate_state_rate, 0.0)
        self.assertEqual(current.budget_fraction, 0.0)
        self.assertFalse(detector.in_impasse())

    def test_progress_resets_counter(self):
        detector = ImpasseDetector(threshold=10.0, patience=2, window=5, budget=100)
        detector.update(False, False, 1)
        detector.update(False, False, 2)
        self.assertGreater(detector.nodes_since_progress, 0)
        detector.update(True, False, 3)
        self.assertEqual(detector.nodes_since_progress, 0)
        current = detector.features()
        self.assertEqual(current.nodes_since_progress, 0.0)

    def test_trigger_after_patience(self):
        detector = ImpasseDetector(threshold=0.1, patience=3, window=5, budget=10)
        fired = False
        for step in range(6):
            fired = detector.update(False, True, step + 1)
        self.assertTrue(fired)
        self.assertTrue(detector.in_impasse())

    def test_no_trigger_with_progress(self):
        detector = ImpasseDetector(threshold=0.9, patience=2, window=5, budget=100)
        fired = detector.update(True, False, 1)
        self.assertFalse(fired)
        fired = detector.update(True, False, 2)
        self.assertFalse(fired)

    def test_reset_clears(self):
        detector = ImpasseDetector(threshold=0.1, patience=1, window=5, budget=10)
        detector.update(False, True, 5)
        self.assertTrue(detector.in_impasse())
        detector.reset()
        self.assertFalse(detector.in_impasse())
        current = detector.features()
        self.assertEqual(current.nodes_since_progress, 0.0)
        self.assertEqual(current.duplicate_state_rate, 0.0)

    def test_deterministic(self):
        first = ImpasseDetector(threshold=0.4, patience=2, window=4, budget=20)
        second = ImpasseDetector(threshold=0.4, patience=2, window=4, budget=20)
        for step in range(4):
            out_first = first.update(False, True, step + 1)
            out_second = second.update(False, True, step + 1)
            self.assertEqual(out_first, out_second)
        self.assertEqual(first.features(), second.features())

    def test_budget_fraction(self):
        detector = ImpasseDetector(threshold=10.0, patience=5, window=5, budget=10)
        detector.update(False, False, 5)
        current = detector.features()
        self.assertAlmostEqual(current.budget_fraction, 0.5)

    def test_budget_term_alone_does_not_trigger(self):
        detector = ImpasseDetector(threshold=0.1, patience=1, window=5, budget=10)
        # progress every step, no duplicates, budget fully consumed
        fired = detector.update(True, False, 10)
        self.assertEqual(detector.features().budget_fraction, 1.0)
        self.assertEqual(detector.score(), 0.0)
        self.assertFalse(fired)

    def test_budget_weight_configurable(self):
        detector = ImpasseDetector(
            threshold=0.1, patience=1, window=5, budget=10, budget_weight=0.2
        )
        fired = detector.update(True, False, 10)
        self.assertAlmostEqual(detector.score(), 0.2)
        self.assertTrue(fired)

    def test_patience_below_one_raises(self):
        with self.assertRaises(ValueError):
            ImpasseDetector(threshold=0.1, patience=0, window=5, budget=10)


if __name__ == "__main__":
    unittest.main()
