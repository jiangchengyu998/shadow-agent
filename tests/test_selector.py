import unittest

from shadow_agent.selector import _best_match, _best_match_with_difflib, select_by_targets


class ManualBoundaryTests(unittest.TestCase):
    def test_target_inside_segments_uses_word_timestamps(self):
        chunks = ['Previous sentence. So, how do scientists calculate the',
                  'effects of climate change? The answer is with models.',
                  'Nothing is certain. Climate models make projections.']
        transcript = []
        clock = 0.0
        for index, text in enumerate(chunks, 1):
            words = []
            start = clock
            for token in text.split():
                words.append({'word': token, 'start': clock, 'end': clock + 0.4})
                clock += 0.5
            transcript.append({'id': index, 'start': start, 'end': clock,
                               'text': text, 'words': words})
        target = 'So, how do scientists calculate the effects of climate change? The answer is with models. Nothing is certain.'
        for matcher in (_best_match, _best_match_with_difflib):
            with self.subTest(matcher=matcher.__name__):
                selected, score = matcher(target, transcript)
                self.assertEqual(selected['text'], target)
                self.assertEqual(selected['start'], transcript[0]['words'][2]['start'])
                self.assertEqual(selected['end'], transcript[2]['words'][2]['end'])
                self.assertEqual(selected['source_ids'], [1, 2, 3])
                self.assertAlmostEqual(score, 100)

    def test_old_transcript_does_not_invent_word_timestamps(self):
        transcript = [{'id': 1, 'start': 1.0, 'end': 5.0,
                       'text': 'Before. The answer is with models. After.'}]
        result = select_by_targets(transcript, ['The answer is with models.'], min_score=0)[0]
        self.assertEqual((result['start'], result['end']), (1.0, 5.0))
        self.assertNotIn('words', result)


if __name__ == '__main__':
    unittest.main()
