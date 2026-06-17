from core.matcher import match_keywords, normalize_text, texts_equal

def test_no_keywords_returns_no_match():
    matched, kw = match_keywords("操作成功", [])
    assert matched is False
    assert kw == ""

def test_single_keyword_match():
    matched, kw = match_keywords("操作成功", ["成功"])
    assert matched is True
    assert kw == "成功"

def test_multiple_keywords_returns_first_match():
    matched, kw = match_keywords("任务完成", ["成功", "完成"])
    assert matched is True
    assert kw == "完成"

def test_no_match_returns_empty():
    matched, kw = match_keywords("普通文本", ["成功", "完成"])
    assert matched is False
    assert kw == ""

def test_empty_text():
    matched, kw = match_keywords("", ["成功"])
    assert matched is False

def test_whitespace_keywords_stripped():
    matched, kw = match_keywords("操作成功", ["  成功  ", "完成"])
    assert matched is True
    assert kw == "成功"


def test_normalize_collapses_whitespace():
    assert normalize_text("a b") == "a b"
    assert normalize_text("a\nb") == "a b"
    assert normalize_text("a   b\tc") == "a b c"
    assert normalize_text("  a  b  ") == "a b"
    assert normalize_text("") == ""


def test_texts_equal_tolerates_ocr_noise():
    # Whitespace differences (the main OCR artifact with EasyOCR line breaks)
    assert texts_equal("操作 成功", "操作\n成功")
    assert texts_equal("  操作  成功  ", "操作 成功")
    # Real content change
    assert not texts_equal("操作成功", "操作失败")
    # Empty / blank
    assert texts_equal("", "")
    assert texts_equal("", "   \n  ")

