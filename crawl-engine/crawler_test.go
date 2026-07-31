package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestExtractLinksBasic(t *testing.T) {
	crawler := NewPageCrawler("https://example.com", "test", 10, 0, false)
	html := `<html><body><a href="/blog/post/">Post</a><a href="/about/">About</a></body></html>`
	links := crawler.ExtractLinks("https://example.com/", html)
	if len(links) != 2 {
		t.Fatalf("expected 2 links, got %d", len(links))
	}
	if links[0].LinkURL != "https://example.com/blog/post/" {
		t.Errorf("first link URL = %q, want https://example.com/blog/post/", links[0].LinkURL)
	}
	if links[0].LinkText != "Post" {
		t.Errorf("first link text = %q, want 'Post'", links[0].LinkText)
	}
}

func TestExtractLinksBaseTag(t *testing.T) {
	crawler := NewPageCrawler("https://example.com", "test", 10, 0, false)
	html := `<html><head><base href="https://example.com/blog/"></head><body><a href="post-name/">Post</a></body></html>`
	links := crawler.ExtractLinks("https://example.com/other/", html)
	if len(links) != 1 {
		t.Fatalf("expected 1 link, got %d", len(links))
	}
	if links[0].LinkURL != "https://example.com/blog/post-name/" {
		t.Errorf("base-resolved URL = %q, want https://example.com/blog/post-name/", links[0].LinkURL)
	}
}

func TestExtractLinksSubdirectory(t *testing.T) {
	crawler := NewPageCrawler("https://example.com", "test", 10, 0, false)
	html := `<html><body><a href="post-one/">Post 1</a><a href="/blog/post-two/">Post 2</a></body></html>`
	links := crawler.ExtractLinks("https://example.com/blog/", html)
	urls := []string{links[0].LinkURL, links[1].LinkURL}
	if urls[0] != "https://example.com/blog/post-one/" {
		t.Errorf("relative URL = %q, want https://example.com/blog/post-one/", urls[0])
	}
	if urls[1] != "https://example.com/blog/post-two/" {
		t.Errorf("absolute URL = %q, want https://example.com/blog/post-two/", urls[1])
	}
}

func TestExtractLinksSkipsMailtoJavascript(t *testing.T) {
	crawler := NewPageCrawler("https://example.com", "test", 10, 0, false)
	html := `<html><body>
		<a href="mailto:test@example.com">Email</a>
		<a href="javascript:void(0)">Click</a>
		<a href="/blog/real/">Real</a>
	</body></html>`
	links := crawler.ExtractLinks("https://example.com/blog/", html)
	if len(links) != 1 {
		t.Fatalf("expected 1 link (mailto/js skipped), got %d", len(links))
	}
	if links[0].LinkURL != "https://example.com/blog/real/" {
		t.Errorf("URL = %q, want https://example.com/blog/real/", links[0].LinkURL)
	}
}

func TestExtractLinksInternalExternal(t *testing.T) {
	crawler := NewPageCrawler("https://example.com", "test", 10, 0, false)
	html := `<html><body>
		<a href="https://other.com/page">External</a>
		<a href="/blog/post/">Internal</a>
	</body></html>`
	links := crawler.ExtractLinks("https://example.com/blog/", html)
	if len(links) != 2 {
		t.Fatalf("expected 2 links, got %d", len(links))
	}
	var internal, external *ExtractedLink
	for i := range links {
		if links[i].IsInternal {
			internal = &links[i]
		} else {
			external = &links[i]
		}
	}
	if internal == nil || external == nil {
		t.Fatal("expected one internal and one external link")
	}
	if !internal.IsInternal {
		t.Error("internal link should be internal")
	}
	if external.IsInternal {
		t.Error("external link should not be internal")
	}
}

func TestExtractLinksImgScriptLink(t *testing.T) {
	crawler := NewPageCrawler("https://example.com", "test", 10, 0, false)
	html := `<html><head>
		<link href="/style.css" rel="stylesheet">
		<script src="/app.js"></script>
		</head><body>
		<img src="/img/photo.png" alt="Photo">
		</body></html>`
	links := crawler.ExtractLinks("https://example.com/", html)
	if len(links) != 3 {
		t.Fatalf("expected 3 links (link, script, img), got %d", len(links))
	}
	types := map[string]bool{}
	for _, l := range links {
		types[l.ElementType] = true
	}
	if !types["link"] || !types["script"] || !types["img"] {
		t.Errorf("missing element types, got: %v", types)
	}
}

func TestExtractLinksMixedContent(t *testing.T) {
	crawler := NewPageCrawler("https://example.com", "test", 10, 0, false)
	html := `<html><body>
		<img src="http://example.com/insecure.png" alt="Insecure">
		</body></html>`
	links := crawler.ExtractLinks("https://example.com/secure-page/", html)
	if len(links) != 1 {
		t.Fatalf("expected 1 link, got %d", len(links))
	}
	if !links[0].IsMixedContent {
		t.Error("expected mixed content flag for HTTP img on HTTPS page")
	}
}

func TestCrawlPageWithMockedServer(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/html")
		w.Write([]byte(`<html><body><a href="/page1/">P1</a><a href="/page2/">P2</a></body></html>`))
	}))
	defer srv.Close()

	crawler := NewPageCrawler(srv.URL, "test", 10, 0, false)
	links := crawler.CrawlPage(srv.URL + "/")
	if len(links) != 2 {
		t.Fatalf("expected 2 links from crawled page, got %d", len(links))
	}
}

func TestCrawlPageWithHTML(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/html")
		w.Write([]byte(`<html><body><a href="/page/">Page</a></body></html>`))
	}))
	defer srv.Close()

	crawler := NewPageCrawler(srv.URL, "test", 10, 0, false)
	links, htmlContent := crawler.CrawlPageWithHTML(srv.URL + "/")
	if len(links) != 1 {
		t.Fatalf("expected 1 link, got %d", len(links))
	}
	if htmlContent == "" {
		t.Error("expected non-empty HTML content")
	}
}

func TestCrawlPageFetchFailure(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(500)
	}))
	defer srv.Close()

	crawler := NewPageCrawler(srv.URL, "test", 10, 0, false)
	links := crawler.CrawlPage(srv.URL + "/broken")
	if links != nil {
		t.Errorf("expected nil links on fetch failure, got %d", len(links))
	}
}

func TestExtractLinksLinkText(t *testing.T) {
	crawler := NewPageCrawler("https://example.com", "test", 10, 0, false)
	html := `<html><body><a href="/blog/post/">My Blog Post Title</a></body></html>`
	links := crawler.ExtractLinks("https://example.com/blog/", html)
	if len(links) != 1 {
		t.Fatalf("expected 1 link, got %d", len(links))
	}
	if links[0].LinkText != "My Blog Post Title" {
		t.Errorf("link text = %q, want 'My Blog Post Title'", links[0].LinkText)
	}
}
