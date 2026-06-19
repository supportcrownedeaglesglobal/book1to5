import unittest
from build_guide_index import build_map

class T(unittest.TestCase):
    def test_shape_and_excerpt(self):
        tracks = [{"id":"001-intro","title":"Introduction","level":1,
                   "segments":[{"role":"chapter_title","text":"Introduction"},
                               {"role":"body","text":"Word "*200}]}]
        m = build_map({5: tracks})
        self.assertIn("001-intro", m)
        e = m["001-intro"]
        self.assertEqual(e["book"], 5)
        self.assertEqual(e["url"], "book-5.html#001-intro")
        self.assertLessEqual(len(e["excerpt"].split()), 160)
if __name__ == "__main__": unittest.main()
