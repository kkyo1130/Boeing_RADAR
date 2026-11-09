import unittest
from compare_unseen_whisper import distance, metrics, words
from summarize_unseen_whisper import bootstrap, summary, error_types

class MetricTests(unittest.TestCase):
    def test_edit_distance_handles_empty_insert_delete_substitute(self):
        self.assertEqual(distance(['one'],[]),1)
        self.assertEqual(distance([],['one','two']),2)
        self.assertEqual(distance(['turn','left'],['turn','right']),1)
    def test_number_format_is_normalized_without_correcting_errors(self):
        self.assertEqual(metrics('heading zero eight zero','Heading 080.')['errors'],0)
        self.assertEqual(metrics('heading two seven zero','heading to seven zero')['errors'],1)
        self.assertFalse(metrics('eight two zero','eight six zero')['numeric_sequence_exact'])
    def test_numbers_are_ordered_and_hallucinations_count(self):
        m=metrics('one two turn left','two one turn left three')
        self.assertGreater(m['numeric_errors'],0)
        self.assertFalse(m['numeric_sequence_exact'])
    def test_summary_uses_corpus_weighted_wer(self):
        rows=[{'reference':'one','transcript':'two','metrics':metrics('one','two'),'seconds':1,'duration':1},
              {'reference':'one two three four five six seven eight nine','transcript':'one two three four five six seven eight nine','metrics':metrics('one two three four five six seven eight nine','one two three four five six seven eight nine'),'seconds':2,'duration':2}]
        self.assertEqual(summary(rows)['wer'],0.1)
    def test_error_types_keep_insertions_and_deletions(self):
        self.assertEqual(error_types('turn left','turn right now'),{'substitutions':1,'deletions':0,'insertions':1})
        self.assertEqual(error_types('turn left',''),{'substitutions':0,'deletions':2,'insertions':0})
    def test_paired_identical_results_have_zero_interval(self):
        row={'metrics':{'errors':2,'reference_words':10}}
        result=bootstrap([(row,row)],100)
        self.assertEqual(result['lower_95'],0);self.assertEqual(result['upper_95'],0)

if __name__=='__main__':unittest.main()
