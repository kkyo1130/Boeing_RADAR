"""Scoring tests: no trained weights needed."""
import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('comparison',Path(__file__).with_name('compare_atc_stt.py'))
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class WordErrorTests(unittest.TestCase):
    def test_empty_hypothesis_is_full_deletion(self):
        self.assertEqual(module.word_errors('heading zero four zero','')['wer'],1)
    def test_insertions_can_exceed_one_hundred_percent(self):
        self.assertEqual(module.word_errors('heading','one two three')['wer'],3)
    def test_digit_expansion_does_not_repair_homophones_or_airlines(self):
        self.assertEqual(module.word_errors('heading zero four zero','Heading 040!',True)['wer'],0)
        self.assertGreater(module.word_errors('heading zero four zero','heading oh for oh',True)['wer'],0)
        self.assertGreater(module.word_errors('lufthansa one kilo k','lufthansa one kilo kilo',True)['wer'],0)
    def test_accented_hallucination_stays_one_word(self):
        self.assertEqual(module.normalized_words('RUVANZOVÁN 080'),['ruvanzován','080'])
    def test_pooled_counts_are_available(self):
        self.assertEqual(module.word_errors('one two three','one two four'),{'errors':1,'reference_words':3,'wer':1/3})

if __name__=='__main__':unittest.main()
