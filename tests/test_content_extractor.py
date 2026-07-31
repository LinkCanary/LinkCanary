"""Tests for the heuristic main-content extractor."""

from link_checker.content_extractor import extract_main_text


SIMPLE_ARTICLE = """
<!DOCTYPE html>
<html>
<head><title>My Page</title><script>var x=1;</script><style>body{}</style></head>
<body>
  <header><nav><a href="/">Home</a><a href="/about/">About</a></nav></header>
  <main>
    <article>
      <h1>Hello World</h1>
      <p>This is the main article content about LinkCanary.</p>
      <p>It has multiple paragraphs of meaningful text.</p>
    </article>
  </main>
  <footer>Copyright 2026. All rights reserved.</footer>
  <aside>Related links go here.</aside>
</body>
</html>
"""

NO_SEMANTIC_TAGS = """
<!DOCTYPE html>
<html>
<body>
  <div class="nav"><a href="/">Home</a></div>
  <div id="content">
    <p>This is the main content inside a div with id=content.</p>
    <p>It should be picked up by the content-hint heuristic.</p>
  </div>
  <div class="sidebar">Sidebar junk.</div>
</body>
</html>
"""

LARGEST_DIV_FALLBACK = """
<!DOCTYPE html>
<html>
<body>
  <div><a href="/tiny/">tiny</a></div>
  <div>
    <p>The largest div by text length should win when no semantic tags or
    content-hint ids are present. This block has the most visible text.</p>
  </div>
</body>
</html>
"""

EMPTY_HTML = "<html><body></body></html>"


class TestExtractMainText:

    def test_strips_script_style_nav_footer(self):
        text = extract_main_text(SIMPLE_ARTICLE)
        assert "var x=1" not in text
        assert "body{}" not in text
        assert "Home" not in text
        assert "About" not in text
        assert "Copyright 2026" not in text
        assert "Related links" not in text

    def test_keeps_article_content(self):
        text = extract_main_text(SIMPLE_ARTICLE)
        assert "Hello World" in text
        assert "main article content about LinkCanary" in text
        assert "multiple paragraphs" in text

    def test_picks_main_element_first(self):
        text = extract_main_text(SIMPLE_ARTICLE)
        # <main> should win over <body> fallback
        assert "main article content" in text

    def test_content_hint_div(self):
        text = extract_main_text(NO_SEMANTIC_TAGS)
        assert "main content inside a div with id=content" in text
        assert "Sidebar junk" not in text

    def test_largest_div_fallback(self):
        text = extract_main_text(LARGEST_DIV_FALLBACK)
        assert "largest div by text length should win" in text
        assert "tiny" not in text

    def test_empty_html_returns_empty(self):
        assert extract_main_text(EMPTY_HTML) == ""

    def test_empty_input_returns_empty(self):
        assert extract_main_text("") == ""
        assert extract_main_text("   ") == ""

    def test_truncation(self):
        long_html = "<html><body><main><p>" + ("a" * 10000) + "</p></main></body></html>"
        text = extract_main_text(long_html, max_chars=100)
        assert len(text) <= 100
        assert text.startswith("a")

    def test_whitespace_collapsed(self):
        html = "<html><body><main><p>foo\n\n   bar\t\tbaz</p></main></body></html>"
        text = extract_main_text(html)
        assert text == "foo bar baz"

    def test_malformed_html_does_not_raise(self):
        # Should return something (possibly empty) without raising
        text = extract_main_text("<html><body><main><p>unclosed")
        assert isinstance(text, str)
