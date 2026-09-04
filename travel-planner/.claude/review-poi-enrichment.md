# Code Review: POI Enrichment (images, links, map)

## Bugs Found

### Bug 1: `gather_live_info()` prompt string concatenation missing newline
**File**: `app/llm.py:245-246`
```python
"汇总成简短中文要点;同时请附上每个景点的官网/百科链接(如有)。"
"信息不确定请注明「以官方为准」。请勿编造。\n" + names
```
Two adjacent string literals concatenate without a separator, producing:
`"...链接(如有)。信息不确定..."` — two sentences run together without space or newline. The LLM will still understand it, but it's sloppy.

**Fix**: Add `\n` between the two sentences.

### Bug 2: SVG `map.clientWidth` is 0 on first render
**File**: `app/web/index.html:207`
The `renderPoiMap()` function reads `map.clientWidth` immediately after setting `$('#out').hidden = false`. In some browsers (especially when the element was just unhidden), `clientWidth` can return `0` before layout recalculation. This causes the SVG viewBox to be `0 0` and all dots to render at `(40, 40)` — a single overlapping blob.

**Fix**: Use `requestAnimationFrame` or `setTimeout` to defer SVG generation until after layout, or use fixed dimensions (e.g. `viewBox="0 0 960 280"`).

### Bug 3: `findPoiInText` substring false positive
**File**: `app/web/index.html:173-177`
```js
function findPoiInText(text) {
  for (const [name, poi] of Object.entries(_poiMap)) {
    if (text.includes(name)) return poi;
  }
  return null;
}
```
If a POI is named `大雁塔` and an activity says `今天不去大雁塔了，改去小雁塔`, it will still match `大雁塔` and show the wrong thumbnail/link. Also, if two POIs share a substring (e.g. `西安钟楼` and `钟楼`), the shorter one may match first due to dict iteration order.

**Fix**: Not critical for MVP (activity text is model-generated, not user-written), but worth noting. A proper fix would match on the longest POI name first, or only match when the POI name appears as a distinct token.

## Improvements

### 1. `website` field is never populated
**File**: `app/models.py:95`
The `Poi.website` field was added but no provider sets it. `gather_live_info()` returns text about links but doesn't parse them back into `Poi.website`. Either remove the field or wire it up.

**Recommendation**: Remove `website` for now. It adds dead weight. The `url` (map link) already serves the "go see more" purpose. `gather_live_info()` returns a text summary that the LLM prompt uses — it doesn't structured-parse links back into POI objects.

### 2. Mock POIs have no `lng/lat` — map will always show "insufficient data"
**File**: `app/poi.py:209-229`
The `MockPoiProvider` never sets `lng`/`lat` on its POIs. Since tests and most demos run in mock mode, the interactive map will **always** show the "景点坐标数据不足" message. The map feature is effectively invisible in the default demo flow.

**Fix**: Add realistic `lng/lat` to the `_KNOWN` city mock POIs. For example:
- 兵马俑: lng=109.27, lat=34.38
- 大雁塔: lng=108.96, lat=34.22
- 西安钟楼: lng=108.94, lat=34.26
- 回民街: lng=108.94, lat=34.26

This would make the SVG map actually render in demo mode.

### 3. `_poi_line()` URL format is verbose for LLM context
**File**: `app/llm.py:269-270`
```python
link = f"详情:{p.url}" if p.url else ""
img = f"封面图:{p.image_url}" if p.image_url else ""
```
For mock POIs, `url` is a search URL like `https://uri.amap.com/search?query=秦始皇帝陵博物院(兵马俑)&city=西安` — a 70+ character string per POI. With 8 POIs × 2 keywords = 16 POIs, that's ~1100 extra characters of URL noise in the LLM prompt. The LLM doesn't need these URLs to plan an itinerary.

**Recommendation**: Only include `link`/`img` in `_poi_line()` when using real providers (not mock). Or better, omit them entirely from the LLM prompt — the URLs are for the UI, not for planning logic.

### 4. Tencent `imgs` field name may be wrong
**File**: `app/poi.py:117`
```python
imgs = it.get("imgs") or []
```
Tencent Map API v1 search response may use `photo` or `images` instead of `imgs`. This is unverified without a real TENCENT_MAP_KEY. The fallback `or []` prevents a crash, but silently produces no images.

**Recommendation**: Add a comment noting this is unverified, or log a warning when the field is empty.

### 5. HTML `title` attribute with emoji doesn't render well in dark mode
**File**: `app/web/index.html:290`
```js
${p.description?`<div class="muted" title="${escapeHtml(p.description)}">ℹ️</div>`:''}
```
The ℹ️ emoji may not render clearly in dark mode (it's blue-on-dark-blue in some browsers). Also, `title` tooltip has a slight delay — a better UX would be inline expansion.

### 6. No `rel="noopener"` on activity map links
**File**: `app/web/index.html:273`
```js
const link = poi.url ? ` <a href="${escapeHtml(poi.url)}" target="_blank" rel="noopener" ...` : '';
```
Actually this one **does** have `rel="noopener"` — good. But the POI table `mapLinkHtml` at line 252 also has it. Consistent. No bug here.

### 7. Lightbox doesn't trap Escape key
**File**: `app/web/index.html:89`
```js
<div id="lightbox" onclick="this.classList.remove('show')">
```
Clicking outside the image closes the lightbox, but pressing Escape does not. Users expect both.

**Fix**: Add a `keydown` listener for Escape.

## Priority Fixes

| Priority | Issue | Effort |
|----------|-------|--------|
| **High** | Bug 2: SVG map clientWidth=0 | 5 min — use fixed viewBox |
| **High** | Improvement 2: Mock POIs need lng/lat | 10 min — add coords to _KNOWN |
| **Medium** | Bug 1: gather_live_info string concat | 1 min — add `\n` |
| **Medium** | Improvement 3: Skip URLs in LLM prompt for mock POIs | 5 min |
| **Low** | Improvement 1: Remove unused `website` field | 2 min |
| **Low** | Improvement 7: Escape key closes lightbox | 3 min |
| **Low** | Improvement 4: Verify Tencent field name | Future — needs real key |
