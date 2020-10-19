from unittest import mock

import numpy as np
import tensorflow as tf

import aspect_based_sentiment_analysis as absa
from aspect_based_sentiment_analysis import BasicPatternRecognizer
from aspect_based_sentiment_analysis import Example
from aspect_based_sentiment_analysis import PredictedExample
from aspect_based_sentiment_analysis import alignment
from aspect_based_sentiment_analysis import Output


def test_basic_pattern_recognizer_call():
    text = ("We are great fans of Slack, but we wish the subscriptions "
            "were more accessible to small startups.")
    example = Example(text, aspect='price')
    recognizer = BasicPatternRecognizer()
    nlp = absa.load('absa/classifier-rest-0.1', pattern_recognizer=recognizer)
    predictions = nlp.transform([example])
    prediction = next(predictions)
    assert isinstance(prediction, PredictedExample)
    assert not prediction.review.is_reference
    assert len(prediction.review.patterns) == 5
    pattern, *_ = prediction.review.patterns
    assert pattern.importance == 1
    assert list(zip(pattern.tokens, pattern.weights)) == \
           [('we', 0.06), ('are', 0.13), ('great', 0.26), ('fans', 0.08),
            ('of', 0.04), ('slack', 0.05), (',', 0.09), ('but', 0.37),
            ('we', 0.23), ('wish', 1.0), ('the', 0.28), ('subscriptions', 0.21),
            ('were', 0.42), ('more', 0.67), ('accessible', 0.2), ('to', 0.26),
            ('small', 0.11), ('startups', 0.22), ('.', 0.18)]


def test_basic_pattern_recognizer_text_token_indices():
    example = mock.Mock()
    example.text_tokens = ['we', 'are', 'soooo', 'great', 'fans', 'of', 'slack']
    example.tokens = ['[CLS]', *example.text_tokens, '[SEP]', 'slack', '[SEP]']
    mask = BasicPatternRecognizer.text_tokens_mask(example)
    assert mask == [False, True, True, True, True, True, True, True, False, False, False]


def test_basic_pattern_recognizer_transform(monkeypatch):
    recognizer = BasicPatternRecognizer(
        max_patterns=3, is_scaled=False, is_rounded=False)
    monkeypatch.setattr(alignment, "merge_tensor", lambda x, **kwargs: x)
    x = tf.constant([[0, 1, 2, 0],
                     [0, 1, 3, 0],
                     [0, 2, 4, 0],
                     [0, 0, 0, 0]], dtype=float)
    x = tf.reshape(x, [1, 1, 4, 4])
    text_mask = [False, True, True, False]
    output = Output(
        scores=None,
        attentions=x,
        attention_grads=tf.ones_like(x, dtype=float),
        hidden_states=None)
    w, pattern_vectors = recognizer.transform(
        output, text_mask, token_subtoken_alignment=None)
    assert w.tolist() == [0.5, 1]
    assert pattern_vectors.tolist() == [[1., 1.],  # [3 3] / [3]
                                        [.5, 1.]]  # [2 4] / [4]

    recognizer = BasicPatternRecognizer(
        max_patterns=3, is_scaled=True, is_rounded=True)
    w, pattern_vectors = recognizer.transform(
        output, text_mask, token_subtoken_alignment=None)
    assert w.tolist() == [0.5, 1]
    assert pattern_vectors.tolist() == [[.5, .5],
                                        [.5, 1.]]


def test_basic_pattern_recognizer_build_patterns():
    recognizer = BasicPatternRecognizer(
        max_patterns=3, is_scaled=False, is_rounded=False)
    w = np.array([0, 3, 2, 0, 1])
    pattern_vectors = np.array([[0, 0, 0],
                                [1, 1, 1],
                                [2, 2, 2],
                                [3, 3, 3],
                                [4, 4, 4]])
    exemplary_tokens = list('abcde')
    patterns = recognizer.build_patterns(w, exemplary_tokens, pattern_vectors)
    assert len(patterns) == 3
    assert all(p.tokens == exemplary_tokens for p in patterns)
    assert [p.importance for p in patterns] == [3, 2, 1]
    assert [p.weights for p in patterns] == [[1, 1, 1],
                                             [2, 2, 2],
                                             [4, 4, 4]]
    w = np.array([1, 3, 2, 0, 1])
    patterns = recognizer.build_patterns(w, exemplary_tokens, pattern_vectors)
    assert len(patterns) == 3
    *_, pattern_3 = patterns
    assert pattern_3.importance == 1
    assert pattern_3.weights == [0, 0, 0]
