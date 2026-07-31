package main

import (
	"crypto/tls"
	"fmt"
	"net/http"
	"net/url"
	"strings"
	"sync"
	"time"
)

// --- Link checker with HEAD/GET, redirect tracing, retry ---
// Port of link_checker/checker.py

const MaxRedirects = 10

var RetryStatusCodes = map[int]bool{502: true, 503: true, 504: true}

type LinkChecker struct {
	UserAgent     string
	Timeout       time.Duration
	Delay         time.Duration
	MaxRetries    int
	RetryDelay    time.Duration
	RetryBackoff  float64
	AuthUser      string
	AuthPass      string
	CustomHeaders map[string]string
	Cookies       map[string]string

	Client *http.Client

	cache           map[string]LinkStatus
	headBlacklist   map[string]bool
	hostDelays      map[string]time.Duration
	lastRequestTime map[string]time.Time
	retryStats      map[string]int
	mu              sync.Mutex
}

func NewLinkChecker(userAgent string, timeoutSec int, delaySec float64, maxRetries int, retryDelaySec, retryBackoff float64) *LinkChecker {
	lc := &LinkChecker{
		UserAgent:     userAgent,
		Timeout:       time.Duration(timeoutSec) * time.Second,
		Delay:         time.Duration(delaySec * float64(time.Second)),
		MaxRetries:    maxRetries,
		RetryDelay:    time.Duration(retryDelaySec * float64(time.Second)),
		RetryBackoff:  retryBackoff,
		CustomHeaders: make(map[string]string),
		Cookies:       make(map[string]string),
		Client: &http.Client{
			Timeout: time.Duration(timeoutSec) * time.Second,
			CheckRedirect: func(req *http.Request, via []*http.Request) error {
				return http.ErrUseLastResponse // Don't follow redirects automatically
			},
			Transport: &http.Transport{
				TLSClientConfig: &tls.Config{InsecureSkipVerify: false},
			},
		},
		cache:           make(map[string]LinkStatus),
		headBlacklist:   make(map[string]bool),
		hostDelays:      make(map[string]time.Duration),
		lastRequestTime: make(map[string]time.Time),
		retryStats:      make(map[string]int),
	}
	return lc
}

func (lc *LinkChecker) getHostDelay(rawURL string) time.Duration {
	host := GetDomain(rawURL)
	lc.mu.Lock()
	defer lc.mu.Unlock()
	if d, ok := lc.hostDelays[host]; ok {
		return d
	}
	return lc.Delay
}

func (lc *LinkChecker) increaseHostDelay(rawURL string) {
	host := GetDomain(rawURL)
	lc.mu.Lock()
	defer lc.mu.Unlock()
	current := lc.Delay
	if d, ok := lc.hostDelays[host]; ok {
		current = d
	}
	newDelay := current * 2
	if newDelay > 30*time.Second {
		newDelay = 30 * time.Second
	}
	lc.hostDelays[host] = newDelay
}

func (lc *LinkChecker) rateLimit(rawURL string) {
	host := GetDomain(rawURL)
	lc.mu.Lock()
	lastTime := lc.lastRequestTime[host]
	lc.mu.Unlock()
	delay := lc.getHostDelay(rawURL)
	elapsed := time.Since(lastTime)
	if elapsed < delay {
		time.Sleep(delay - elapsed)
	}
	lc.mu.Lock()
	lc.lastRequestTime[host] = time.Now()
	lc.mu.Unlock()
}

func (lc *LinkChecker) shouldUseGet(rawURL string) bool {
	host := GetDomain(rawURL)
	lc.mu.Lock()
	defer lc.mu.Unlock()
	return lc.headBlacklist[host]
}

func (lc *LinkChecker) addToHeadBlacklist(rawURL string) {
	host := GetDomain(rawURL)
	lc.mu.Lock()
	defer lc.mu.Unlock()
	lc.headBlacklist[host] = true
}

func (lc *LinkChecker) makeRequest(rawURL, method string) (*http.Response, float64) {
	lc.rateLimit(rawURL)

	var bodyReader *strings.Reader
	if method == "GET" {
		bodyReader = strings.NewReader("")
	}

	var req *http.Request
	var err error
	if method == "GET" && bodyReader != nil {
		req, err = http.NewRequest("GET", rawURL, bodyReader)
	} else {
		req, err = http.NewRequest(method, rawURL, nil)
	}
	if err != nil {
		return nil, 0
	}

	req.Header.Set("User-Agent", lc.UserAgent)
	req.Header.Set("Accept", "*/*")
	for k, v := range lc.CustomHeaders {
		req.Header.Set(k, v)
	}
	for k, v := range lc.Cookies {
		req.AddCookie(&http.Cookie{Name: k, Value: v})
	}
	if lc.AuthUser != "" && lc.AuthPass != "" {
		req.SetBasicAuth(lc.AuthUser, lc.AuthPass)
	}

	start := time.Now()
	resp, err := lc.Client.Do(req)
	elapsedMs := float64(time.Since(start).Microseconds()) / 1000.0
	if err != nil {
		return nil, 0
	}
	return resp, elapsedMs
}

func (lc *LinkChecker) makeRequestWithRetry(rawURL, method string) (*http.Response, int, float64) {
	retryCount := 0
	currentDelay := lc.RetryDelay

	for retryCount <= lc.MaxRetries {
		resp, elapsedMs := lc.makeRequest(rawURL, method)

		if resp == nil {
			if retryCount < lc.MaxRetries {
				retryCount++
				time.Sleep(currentDelay)
				currentDelay = time.Duration(float64(currentDelay) * lc.RetryBackoff)
				continue
			}
			return nil, retryCount, elapsedMs
		}

		if !RetryStatusCodes[resp.StatusCode] {
			return resp, retryCount, elapsedMs
		}

		if retryCount < lc.MaxRetries {
			retryCount++
			time.Sleep(currentDelay)
			currentDelay = time.Duration(float64(currentDelay) * lc.RetryBackoff)
		} else {
			return resp, retryCount, elapsedMs
		}
	}
	return nil, retryCount, 0
}

func (lc *LinkChecker) checkSingleURL(rawURL string) (int, string, string, int, float64) {
	useGet := lc.shouldUseGet(rawURL)
	var retryCount int
	var elapsedMs float64
	var resp *http.Response

	if !useGet {
		resp, retryCount, elapsedMs = lc.makeRequestWithRetry(rawURL, "HEAD")
		if resp != nil {
			if resp.StatusCode == 403 || resp.StatusCode == 405 || resp.StatusCode == 501 {
				lc.addToHeadBlacklist(rawURL)
				resp.Body.Close()
				useGet = true
			} else {
				location := resp.Header.Get("Location")
				status := resp.StatusCode
				resp.Body.Close()
				return status, location, "", retryCount, elapsedMs
			}
		}
	}

	if useGet || resp == nil {
		resp, retryCount, elapsedMs = lc.makeRequestWithRetry(rawURL, "GET")
	}

	if resp == nil {
		return 0, "", "Request failed (timeout or connection error)", retryCount, elapsedMs
	}

	if resp.StatusCode == 429 {
		lc.increaseHostDelay(rawURL)
		time.Sleep(lc.getHostDelay(rawURL))
		resp.Body.Close()
		resp, retryCount, elapsedMs = lc.makeRequestWithRetry(rawURL, "GET")

		if resp == nil || resp.StatusCode == 429 {
			lc.increaseHostDelay(rawURL)
			time.Sleep(lc.getHostDelay(rawURL))
			if resp != nil {
				resp.Body.Close()
			}
			resp, retryCount, elapsedMs = lc.makeRequestWithRetry(rawURL, "GET")

			if resp == nil || resp.StatusCode == 429 {
				if resp != nil {
					resp.Body.Close()
				}
				return 429, "", "Rate limited after retries", retryCount, elapsedMs
			}
		}
	}

	location := resp.Header.Get("Location")
	status := resp.StatusCode
	resp.Body.Close()
	return status, location, "", retryCount, elapsedMs
}

// CheckLink checks a URL's status, following redirects and detecting issues.
func (lc *LinkChecker) CheckLink(rawURL string) LinkStatus {
	lc.mu.Lock()
	if cached, ok := lc.cache[rawURL]; ok {
		lc.mu.Unlock()
		return cached
	}
	lc.mu.Unlock()

	var chain [][2]string
	visited := make(map[string]bool)
	currentURL := rawURL
	isLoop := false
	errMsg := ""
	totalRetries := 0
	var firstResponseTimeMs *float64

	for i := 0; i < MaxRedirects+1; i++ {
		if visited[currentURL] {
			isLoop = true
			break
		}
		visited[currentURL] = true

		statusCode, location, reqError, retryCount, elapsedMs := lc.checkSingleURL(currentURL)
		totalRetries += retryCount

		if firstResponseTimeMs == nil {
			firstResponseTimeMs = &elapsedMs
		}

		if reqError != "" {
			errMsg = reqError
			chain = append(chain, [2]string{"0", currentURL})
			break
		}

		chain = append(chain, [2]string{fmt.Sprintf("%d", statusCode), currentURL})

		if statusCode < 300 || statusCode >= 400 {
			break
		}
		if location == "" {
			break
		}
		if !strings.HasPrefix(location, "http") {
			location = ResolveRelativeURL(currentURL, location)
		}
		currentURL = location
	}

	var finalStatus int
	var finalURL string
	if len(chain) > 0 {
		fmt.Sscanf(chain[len(chain)-1][0], "%d", &finalStatus)
		finalURL = chain[len(chain)-1][1]
	} else {
		finalURL = rawURL
	}

	isRedirect := len(chain) > 1
	isCanonical := false
	if isRedirect && len(chain) == 2 && !isLoop {
		isCanonical = IsCanonicalRedirect(rawURL, finalURL)
	}

	result := LinkStatus{
		URL:              rawURL,
		StatusCode:       finalStatus,
		IsRedirect:       isRedirect,
		RedirectChain:    chain,
		FinalURL:         finalURL,
		IsLoop:           isLoop,
		IsCanonicalRedir: isCanonical,
		Error:            errMsg,
		Retries:          totalRetries,
	}
	if firstResponseTimeMs != nil {
		result.ResponseTimeMs = *firstResponseTimeMs
	}

	lc.mu.Lock()
	lc.cache[rawURL] = result
	lc.mu.Unlock()
	return result
}

// CheckLinks checks multiple URLs sequentially.
func (lc *LinkChecker) CheckLinks(urls []string) map[string]LinkStatus {
	results := make(map[string]LinkStatus)
	for _, u := range urls {
		results[u] = lc.CheckLink(u)
	}
	return results
}

// GetRetryStats returns retry statistics.
func (lc *LinkChecker) GetRetryStats() (int, int) {
	totalRetries := 0
	urlsWithRetries := 0
	lc.mu.Lock()
	defer lc.mu.Unlock()
	for _, status := range lc.cache {
		totalRetries += status.Retries
		if status.Retries > 0 {
			urlsWithRetries++
		}
	}
	return urlsWithRetries, totalRetries
}

// ToJSONStatus converts a LinkStatus to its JSON-serializable form.
func (ls *LinkStatus) ToJSONStatus() JSONLinkStatus {
	hops := make([]JSONRedirectHop, len(ls.RedirectChain))
	for i, hop := range ls.RedirectChain {
		var statusInt int
		fmt.Sscanf(hop[0], "%d", &statusInt)
		hops[i] = JSONRedirectHop{Status: statusInt, URL: hop[1]}
	}
	return JSONLinkStatus{
		URL:              ls.URL,
		StatusCode:       ls.StatusCode,
		IsRedirect:       ls.IsRedirect,
		RedirectChain:    hops,
		FinalURL:         ls.FinalURL,
		IsLoop:           ls.IsLoop,
		IsCanonicalRedir: ls.IsCanonicalRedir,
		Error:            ls.Error,
		Retries:          ls.Retries,
		ResponseTimeMs:   ls.ResponseTimeMs,
	}
}

// Ensure url.Parse is referenced (used indirectly via ResolveRelativeURL)
var _ = url.Parse
