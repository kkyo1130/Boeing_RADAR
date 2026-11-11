import importlib.util,tempfile,unittest,wave
from pathlib import Path
import numpy as np
spec=importlib.util.spec_from_file_location('specialists',Path(__file__).with_name('compare_atc_specialists.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class SpecialistTests(unittest.TestCase):
    def test_resampling_preserves_duration_and_silence(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'quiet.wav'
            with wave.open(str(path),'wb') as w:
                w.setparams((1,2,8000,0,'NONE','not compressed'));w.writeframes(bytes(16000))
            samples,rate=m.pcm16(path,16000)
            self.assertEqual(rate,16000);self.assertEqual(len(samples),16000)
            self.assertTrue(np.all(samples==0))
    def test_text_gate_does_not_accept_wrong_call_or_extra_field(self):
        p={'instruction_check':'PASS','callsign':{'value':'GWI7P'},'fields':{'HDG':{'value':40}}}
        self.assertTrue(m.text_gate(p,'GWI7P',40))
        self.assertFalse(m.text_gate(p,'OTHER',40))
        self.assertFalse(m.text_gate(p,'GWI7P',300))
        p['fields']['ALT']={'value':3000};self.assertFalse(m.text_gate(p,'GWI7P',40))

if __name__=='__main__':unittest.main()
