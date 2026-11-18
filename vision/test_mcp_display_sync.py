import unittest
from unittest.mock import patch
from mcp_display_sync import DisplaySync, validate_labels, PRESETS

class SyncTests(unittest.TestCase):
    def test_labels(self):
        for h,a in PRESETS: validate_labels(h,a)
        for h,a in [('360','03000'),('090','99999'),('90','03000')]:
            with self.assertRaises(ValueError): validate_labels(h,a)

    def test_ack_settle_disconnect_and_wrong_command(self):
        sync=DisplaySync('http://unused','tablet')
        state=dict(seq='unique',client='tablet',heading=120,altitude=5500,ready=False)
        with patch.object(sync,'request',return_value=state): sync.set('120','05500')
        with patch.object(sync,'request',return_value=state): self.assertFalse(sync.ready())
        with patch.object(sync,'request',return_value={**state,'ready':True}), patch('mcp_display_sync.time.monotonic',side_effect=[10,10,12]):
            self.assertFalse(sync.ready()); self.assertTrue(sync.ready())
        with patch.object(sync,'request',side_effect=OSError('offline')): self.assertFalse(sync.ready())
        with patch.object(sync,'request',return_value={**state,'ready':True,'seq':'other'}): self.assertFalse(sync.ready())
        sync.command=None
        with patch.object(sync,'request',return_value={**state,'ready':True}): self.assertFalse(sync.ready())

if __name__=='__main__': unittest.main()
