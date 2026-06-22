from core.matcher import contains_any_keyword, match_keywords, normalize_text, texts_equal, _ocr_normalize

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
    # Whitespace differences (the main OCR artifact with line-break shifts)
    assert texts_equal("操作 成功", "操作\n成功")
    assert texts_equal("  操作  成功  ", "操作 成功")
    # Real content change
    assert not texts_equal("操作成功", "操作失败")
    # Empty / blank
    assert texts_equal("", "")
    assert texts_equal("", "   \n  ")


def test_contains_any_keyword_empty_is_no_hit():
    """Empty keyword list or empty text must not trigger the gate."""
    hit, kw = contains_any_keyword("操作成功", [])
    assert hit is False
    assert kw == ""
    hit, kw = contains_any_keyword("", ["失败", "异常"])
    assert hit is False
    assert kw == ""


def test_contains_any_keyword_hit():
    hit, kw = contains_any_keyword("订单失败，请重试", ["失败", "异常"])
    assert hit is True
    assert kw == "失败"


def test_contains_any_keyword_substring_match():
    """Substring containment, not whole-word. '失败' must hit '订单失败中'."""
    hit, _ = contains_any_keyword("订单失败中", ["失败"])
    assert hit is True


def test_contains_any_keyword_whitespace_stripped():
    hit, kw = contains_any_keyword("网络异常", ["  异常  ", "失败"])
    assert hit is True
    assert kw == "异常"


def test_ocr_normalize_merges_ji_yi_pair():
    # Canonical form is 己, so 已 normalizes to 己. 己 stays as 己.
    assert _ocr_normalize("自己") == "自己"
    assert _ocr_normalize("自已") == "自己"
    assert _ocr_normalize("自己的厂房") == "自己的厂房"
    assert _ocr_normalize("自已的厂房") == "自己的厂房"
    # Idempotent: normalizing twice == once.
    once = _ocr_normalize("自已的厂房")
    twice = _ocr_normalize(once)
    assert once == twice == "自己的厂房"
    # Other chars pass through untouched.
    assert _ocr_normalize("网络异常") == "网络异常"
    assert _ocr_normalize("") == ""


def test_ocr_normalize_does_not_touch_other_similar_chars():
    # Guard rail: only 己/已 are merged. 千/干, 末/未, 士/土 stay distinct.
    assert _ocr_normalize("千") == "千"
    assert _ocr_normalize("干") == "干"
    assert _ocr_normalize("末") == "末"
    assert _ocr_normalize("未") == "未"
    assert _ocr_normalize("士") == "士"
    assert _ocr_normalize("土") == "土"


def test_exclude_ji_yi_confusable_hits():
    """Regression: OCR reads 己 as 已 in '自己的厂房' -> '自已的厂房'."""
    ocr = "我是自已的厂房，目前设计图纸出来了"
    hit, kw = contains_any_keyword(ocr, ["自己的厂房"])
    assert hit is True
    assert kw == "自己的厂房"


def test_exclude_other_direction_also_hits():
    """User can enter either form; both should match OCR output."""
    ocr = "我是自己的厂房，目前设计图纸出来了"
    hit_a, _ = contains_any_keyword(ocr, ["自己的厂房"])
    hit_b, _ = contains_any_keyword(ocr, ["自已的厂房"])
    assert hit_a is True
    assert hit_b is True


def test_exclude_unchanged_for_unrelated_keywords():
    """Sanity: normal keywords still behave exactly like before."""
    hit, kw = contains_any_keyword("操作成功", ["失败", "异常"])
    assert hit is False
    assert kw == ""

