import json

import responses

HEADER = {"site": "x", "action": "tweets"}


def test_payload_is_one_json_text_block_keeping_unicode():
    content = responses.to_text_content({"name": "Катя"})

    assert len(content) == 1
    assert content[0].type == "text"
    assert content[0].text == '{"name": "Катя"}'


def test_small_response_keeps_all_items_and_is_not_marked_truncated():
    response = responses.fit_items(HEADER, [{"text": "hi"}])

    assert response == {**HEADER, "count": 1, "items": [{"text": "hi"}]}


def test_empty_items_give_empty_response():
    assert responses.fit_items(HEADER, []) == {**HEADER, "count": 0, "items": []}


def test_large_response_drops_items_from_the_end(monkeypatch):
    monkeypatch.setattr(responses, "MAX_RESPONSE_CHARS", 200)
    items = [{"text": f"{index}" + "x" * 60} for index in range(5)]

    response = responses.fit_items(HEADER, items)

    assert response["truncated"] is True
    assert response["items"] == items[: response["count"]]
    assert 0 < response["count"] < 5
    assert len(json.dumps(response)) <= 200


def test_item_larger_than_limit_returns_explanation_instead_of_silent_empty(monkeypatch):
    monkeypatch.setattr(responses, "MAX_RESPONSE_CHARS", 100)

    response = responses.fit_items(HEADER, [{"text": "x" * 500}, {"text": "y" * 500}])

    assert response["count"] == 0
    assert response["items"] == []
    assert response["truncated"] is True
    assert "larger than the 100-character response limit" in response["message"]


SECTION_HEADER = {"site": "linkedin", "action": "profile", "requests_left_today": 44}


def test_small_section_answer_is_returned_whole():
    result = {"url": "https://x/", "sections": {"main_profile": "Jane"}}

    assert responses.fit_sections(SECTION_HEADER, result) == {**SECTION_HEADER, **result}


def test_longest_sections_are_cut_until_the_answer_fits_and_named():
    result = {
        "url": "https://x/",
        "sections": {"main_profile": "Jane", "posts": "p" * 30_000, "experience": "e" * 12_000},
        "references": {"posts": [{"kind": "feed_post", "url": "/feed/update/1/"}]},
    }

    response = responses.fit_sections(SECTION_HEADER, result)

    assert len(json.dumps(response, ensure_ascii=False)) <= responses.MAX_RESPONSE_CHARS
    assert response["sections"]["main_profile"] == "Jane"
    assert response["sections"]["posts"].endswith(responses.CUT_MARKER)
    assert response["truncated_sections"] == ["posts", "experience"] or response["truncated_sections"] == ["posts"]
    assert response["references"] == result["references"]
    assert result["sections"]["posts"] == "p" * 30_000


def test_links_are_dropped_last_when_text_alone_cannot_make_it_fit(monkeypatch):
    monkeypatch.setattr(responses, "MAX_RESPONSE_CHARS", 400)
    result = {
        "url": "https://x/",
        "sections": {"main_profile": "Jane " * 20},
        "references": {"main_profile": [{"kind": "person", "url": f"/in/person-{n}/"} for n in range(30)]},
    }

    response = responses.fit_sections(SECTION_HEADER, result)

    assert "references" not in response
    assert response["references_dropped"] is True
    assert len(json.dumps(response, ensure_ascii=False)) <= 400
