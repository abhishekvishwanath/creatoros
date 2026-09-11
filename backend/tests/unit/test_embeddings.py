from app.agent_service.memory.embeddings import EMBEDDING_DIM, embed_text, embed_texts


def test_embed_text_returns_correct_dimension():
    vector = embed_text("a video about productivity tips for students")
    assert vector is not None
    assert len(vector) == EMBEDDING_DIM
    assert all(isinstance(v, float) for v in vector)


def test_embed_text_empty_string_returns_none():
    assert embed_text("") is None
    assert embed_text("   ") is None


def test_embed_text_similar_texts_are_closer_than_dissimilar():
    import math

    def cosine(a, b):
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(y * y for y in b))
        return dot / (na * nb)

    a = embed_text("How to grow your YouTube channel with consistent uploads")
    b = embed_text("Tips for growing a YouTube audience through regular posting")
    c = embed_text("A recipe for chocolate chip cookies")

    assert cosine(a, b) > cosine(a, c)


def test_embed_texts_batch_matches_individual_calls_in_length_and_skips_empty():
    vectors = embed_texts(["hello world", "", "another piece of text"])
    assert len(vectors) == 3
    assert vectors[0] is not None
    assert vectors[1] is None
    assert vectors[2] is not None
