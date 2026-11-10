import unittest
from evaluate_atc_slots import call_key,scored,summarize

class SlotMetricTests(unittest.TestCase):
    def test_call_format_equivalence_without_error_repair(self):
        self.assertEqual(call_key('German Wings 7P'),call_key('german wings seven papa'))
        self.assertEqual(call_key('KLM 04A'),call_key('klm zero four alfa'))
        self.assertNotEqual(call_key('csa seven three two two'),call_key('sierra say seven three two two'))
        self.assertNotEqual(call_key('radar to'),call_key('radar two'))
    def test_wrong_value_is_false_positive_and_missed_target(self):
        self.assertEqual(scored([270],[290]),{'tp':0,'fp':1,'fn':1,'exact':False,'support':1})
    def test_no_target_does_not_become_perfect_recall(self):
        rows=[{'scores':{'HDG':scored([],[])}}]
        result=summarize(rows,'HDG');self.assertIsNone(result['recall']);self.assertIsNone(result['f1'])
        self.assertEqual(result['absent_rows'],1)
    def test_unresolved_and_duplicate_candidates_are_not_silently_discarded(self):
        self.assertEqual(scored([],['UNRESOLVED'])['fp'],1)
        self.assertEqual(scored([270],[270,270])['fp'],1)
    def test_zero_heading_is_a_real_value(self):
        self.assertEqual(scored([0],[0])['tp'],1)
        self.assertEqual(scored([0],[])['fn'],1)
        self.assertEqual(scored([0],['UNRESOLVED'])['fn'],1)
    def test_ambiguous_gold_is_excluded_not_marked_absent(self):
        r=summarize([{'scores':{'CALLSIGN':None}}],'CALLSIGN')
        self.assertEqual(r['absent_rows'],0);self.assertEqual(r['support'],0)

if __name__=='__main__':unittest.main()
