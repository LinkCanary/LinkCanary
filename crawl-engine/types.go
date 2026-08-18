package main

// JSON output types for the crawl engine. The Python CLI parses this
// JSON and converts the structs into its own ExtractedLink / LinkStatus
// / page_html data structures.

// CrawlOutput is the top-level JSON object written to stdout.
type CrawlOutput struct {
	Metadata     Metadata             `json:"metadata"`
	SitemapURLs  []string             `json:"sitemap_urls"`
	PageURLs     []string             `json:"page_urls"`
	Links        []JSONExtractedLink  `json:"links"`
	PageHTML     map[string]string    `json:"page_html"`
	LinkStatuses []JSONLinkStatus     `json:"link_statuses"`
	RobotsStats  JSONRobotsStats      `json:"robots_stats"`
	RetryStats   JSONRetryStats       `json:"retry_stats"`
	BaselineURLs []string             `json:"baseline_urls"`
}

// ErrorOutput is emitted on fatal failure before exiting with code 2.
type ErrorOutput struct {
	Error    string `json:"error"`
	ExitCode int    `json:"exit_code"`
}

type Metadata struct {
	BaseURL      string `json:"base_url"`
	SitemapMode  bool   `json:"sitemap_mode"`
	PageCount    int    `json:"page_count"`
	TotalLinks   int    `json:"total_links"`
	UniqueLinks  int    `json:"unique_links"`
	CheckedLinks int    `json:"checked_links"`
}

type JSONExtractedLink struct {
	SourceURL      string `json:"source_url"`
	LinkURL        string `json:"link_url"`
	LinkText       string `json:"link_text"`
	IsInternal     bool   `json:"is_internal"`
	ElementType    string `json:"element_type"`
	IsMixedContent bool   `json:"is_mixed_content"`
}

type JSONRedirectHop struct {
	Status int    `json:"status"`
	URL    string `json:"url"`
}

type JSONLinkStatus struct {
	URL                string            `json:"url"`
	StatusCode         int               `json:"status_code"`
	IsRedirect         bool              `json:"is_redirect"`
	RedirectChain      []JSONRedirectHop `json:"redirect_chain"`
	FinalURL           string            `json:"final_url"`
	IsLoop             bool              `json:"is_loop"`
	IsCanonicalRedir   bool              `json:"is_canonical_redirect"`
	Error              string            `json:"error"`
	Retries            int               `json:"retries"`
	ResponseTimeMs     float64           `json:"response_time_ms"`
}

type JSONRobotsStats struct {
	URLsSkipped int  `json:"urls_skipped"`
	Ignored     bool `json:"ignored"`
}

type JSONRetryStats struct {
	URLsWithRetries int `json:"urls_with_retries"`
	TotalRetries    int `json:"total_retries"`
}

// ExtractedLink is the internal representation during crawling.
type ExtractedLink struct {
	SourceURL      string
	LinkURL        string
	LinkText       string
	IsInternal     bool
	ElementType    string
	IsMixedContent bool
}

// LinkStatus is the internal representation during link checking.
type LinkStatus struct {
	URL              string
	StatusCode       int
	IsRedirect       bool
	RedirectChain    [][2]string // [status, url] pairs
	FinalURL         string
	IsLoop           bool
	IsCanonicalRedir bool
	Error            string
	Retries          int
	ResponseTimeMs   float64
}
