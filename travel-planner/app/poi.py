"""多平台景点(POI)检索与交叉验证(spec: 多平台交叉检索景点)。

高德/腾讯/百度各用官方 REST 检索本城 POI,然后按「名称归一化」做交叉:
同一景点被 ≥2 个启用平台命中 → verified=True。无 key 或全部失败 → mock 兜底。
"""

from __future__ import annotations

import os
import re
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx

from app.models import Poi

_TIMEOUT = httpx.Timeout(6.0)
_DEFAULT_KW = ["景点"]

_PREF_KEYWORDS = {
    "人文": ["博物馆", "古迹", "历史街区"],
    "美食": ["小吃街", "美食街", "老字号"],
    "自然": ["公园", "山水", "风景区"],
    "亲子": ["游乐园", "动物园", "科技馆"],
    "海滨": ["海滩", "滨海"],
    "购物": ["商圈", "步行街"],
}

# 每个平台在单关键词下最多保留的候选数
_TOP_K = 8


def keywords_for(preferences: list[str]) -> list[str]:
    """偏好 → 检索关键词。无匹配偏好时返回默认「景点」。"""
    kws: list[str] = []
    for pref in preferences:
        for k in _PREF_KEYWORDS.get(pref, []):
            kws.append(k)
    return kws or _DEFAULT_KW


def _norm(name: str, city: str) -> str:
    """名称归一化:去空白、去城市前缀、剥常见后缀,用于跨平台比对。"""
    s = re.sub(r"\s+", "", name)
    if s.startswith(city):
        s = s[len(city):]
    for _ in range(2):
        before = s
        s = re.sub(r"(景区|风景区|旅游区|遗址公园|公园|博物馆)$", "", s)
        if s == before:
            break
    return s


class PoiProvider(ABC):
    """POI 检索源。每个 provider 自己决定密钥与请求。"""

    name: str = "base"

    @abstractmethod
    def search(self, city: str, query: str, client: httpx.Client | None = None) -> list[Poi]:
        """按关键词在 city 检索 POI。失败抛 httpx.HTTPError,由上层剔除该源。"""


class AmapProvider(PoiProvider):
    name = "高德"

    def search(self, city, query, client=None) -> list[Poi]:
        url = "https://restapi.amap.com/v3/place/text"
        params = {"key": os.getenv("AMAP_KEY"), "keywords": query, "city": city, "offset": _TOP_K}
        with (client or httpx.Client(timeout=_TIMEOUT)) as c:
            data = c.get(url, params=params).json()
        pois: list[Poi] = []
        for it in (data.get("pois") or [])[:_TOP_K]:
            loc = it.get("location") or ""
            lng, lat = (loc.split(",") + [None, None])[:2]
            # 提取首张封面图
            photos = it.get("photos") or []
            first_photo = (photos[0].get("url", "") if photos else "") or None
            # 构造高德 POI 详情页 URL
            poi_id = it.get("id", "")
            amap_url = f"https://uri.amap.com/poi/{poi_id}" if poi_id else None
            pois.append(
                Poi(
                    name=it.get("name", ""),
                    address=it.get("address", "") or "",
                    category=(it.get("type") or "").split(";")[-1],
                    sources=[self.name],
                    rating=_f(it.get("biz_ext", {}).get("rating")),
                    url=amap_url,
                    image_url=first_photo,
                )
            )
            pois[-1].lng = _f(lng)
            pois[-1].lat = _f(lat)
        return pois


class TencentProvider(PoiProvider):
    name = "腾讯"

    def search(self, city, query, client=None) -> list[Poi]:
        url = "https://apis.map.qq.com/ws/place/v1/search"
        params = {
            "key": os.getenv("TENCENT_MAP_KEY"),
            "keyword": query,
            "boundary": f"region({city},0)",
            "page_size": _TOP_K,
        }
        with (client or httpx.Client(timeout=_TIMEOUT)) as c:
            data = c.get(url, params=params).json()
        pois: list[Poi] = []
        for it in (data.get("data") or [])[:_TOP_K]:
            loc = it.get("location") or {}
            # 提取首张封面图
            imgs = it.get("imgs") or []
            first_img = (imgs[0] if imgs else None) or None
            # 构造腾讯地图详情页 URL
            poi_id = it.get("id", "")
            tencent_url = f"https://lbs.qq.com/place/poi/{poi_id}" if poi_id else None
            pois.append(
                Poi(
                    name=it.get("title", ""),
                    address=it.get("address", "") or "",
                    category=(it.get("category") or "").split(":")[-1],
                    sources=[self.name],
                    lng=_f(loc.get("lng")),
                    lat=_f(loc.get("lat")),
                    url=tencent_url,
                    image_url=first_img,
                )
            )
        return pois


class BaiduProvider(PoiProvider):
    name = "百度"

    def search(self, city, query, client=None) -> list[Poi]:
        url = "https://api.map.baidu.com/place/v2/search"
        params = {
            "ak": os.getenv("BAIDU_MAP_KEY"),
            "query": query,
            "region": city,
            "output": "json",
            "page_size": _TOP_K,
        }
        with (client or httpx.Client(timeout=_TIMEOUT)) as c:
            data = c.get(url, params=params).json()
        pois: list[Poi] = []
        for it in (data.get("results") or [])[:_TOP_K]:
            loc = it.get("location") or {}
            detail = it.get("detail_info") or {}
            # 提取详情页 URL 和缩略图
            baidu_url = detail.get("detail_url") or None
            thumb = detail.get("thumbnail") or None
            pois.append(
                Poi(
                    name=it.get("name", ""),
                    address=it.get("address", "") or "",
                    category=detail.get("tag", "") or "",
                    sources=[self.name],
                    rating=_f(detail.get("overall_rating")),
                    lng=_f(loc.get("lng")),
                    lat=_f(loc.get("lat")),
                    url=baidu_url,
                    image_url=thumb,
                )
            )
        return pois


def _f(v) -> float | None:
    if v in (None, "", "[]"):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


class MockPoiProvider(PoiProvider):
    """无真实 key 时的兜底:内置真实知名景点,保证零配置可演示。"""

    name = "mock"

    _KNOWN = {
        "西安": [
            (
                "秦始皇帝陵博物院(兵马俑)", "临潼区秦陵北路", "博物馆", 120, 4.9,
                "08:30-18:00", 109.27, 34.38,
            ),
            (
                "大雁塔·大慈恩寺", "雁塔区雁塔南路", "人文古迹", 50, 4.7,
                "08:00-17:30", 108.96, 34.22,
            ),
            ("西安钟楼", "碑林区东大街", "人文古迹", 30, 4.6, "08:30-21:00", 108.94, 34.26),
            ("回民街", "莲湖区北院门", "美食街", 0, 4.4, "全天", 108.93, 34.26),
        ],
        "北京": [
            ("故宫博物院", "东城区景山前街4号", "博物馆", 60, 4.9, "08:30-17:00", 116.40, 39.92),
            ("颐和园", "海淀区新建宫门路19号", "公园", 30, 4.8, "06:30-18:00", 116.27, 39.99),
            ("八达岭长城", "延庆区G6京藏高速", "古迹", 40, 4.8, "07:30-17:30", 116.01, 40.35),
            ("南锣鼓巷", "东城区交道口街道", "历史街区", 0, 4.3, "全天", 116.41, 39.93),
        ],
        "杭州": [
            ("西湖风景名胜区", "西湖区龙井路1号", "风景区", 0, 4.9, "全天", 120.15, 30.25),
            ("灵隐寺", "西湖区法云弄1号", "人文古迹", 75, 4.7, "07:00-18:00", 120.10, 30.24),
            (
                "西溪国家湿地公园", "西湖区天目山路518号", "公园", 80, 4.6,
                "08:30-17:30", 120.06, 30.28,
            ),
            ("河坊街", "上城区河坊街", "历史街区", 0, 4.4, "全天", 120.17, 30.24),
        ],
    }

    def search(self, city, query, client=None) -> list[Poi]:
        entries = self._KNOWN.get(city)
        if not entries:
            search_url = f"https://uri.amap.com/search?query={city}+地标&city={city}"
            return [
                Poi(name=f"{city}·城市地标", address=city, category="景点",
                    sources=[self.name], ticket_price=0.0, is_mock=True,
                    url=search_url)
            ]
        results = []
        for name, addr, cat, ticket, rating, hours, lng, lat in entries:
            search_url = f"https://uri.amap.com/search?query={name}&city={city}"
            results.append(
                Poi(
                    name=name, address=addr, category=cat, sources=[self.name],
                    verified=False, rating=rating, ticket_price=ticket,
                    open_hours=hours, description="内置演示数据(mock)", is_mock=True,
                    url=search_url, lng=lng, lat=lat,
                )
            )
        return results


def resolve_poi_providers(configured: dict[str, bool] | None = None) -> list[PoiProvider]:
    """按 POI_PROVIDERS 与密钥是否配置,返回启用源;一个都没配则只留 mock。"""
    order = {"amap": AmapProvider, "tencent": TencentProvider, "baidu": BaiduProvider}
    key_map = {"amap": "AMAP_KEY", "tencent": "TENCENT_MAP_KEY", "baidu": "BAIDU_MAP_KEY"}
    raw = os.getenv("POI_PROVIDERS", "amap,tencent,baidu")
    providers: list[PoiProvider] = []
    for token in [t.strip() for t in raw.split(",") if t.strip()]:
        cls = order.get(token)
        if not cls or not os.getenv(key_map[token]):
            continue
        providers.append(cls())
    return providers or [MockPoiProvider()]


def search_pois(
    city: str,
    keywords: list[str],
    providers: list[PoiProvider] | None = None,
) -> list[Poi]:
    """并发向所有启用源检索每个关键词,合并后交叉验证。"""
    providers = providers or resolve_poi_providers()
    if not keywords:
        keywords = list(_DEFAULT_KW)

    raw: list[Poi] = []
    jobs = [(p, kw) for p in providers for kw in keywords]
    with ThreadPoolExecutor(max_workers=max(4, len(jobs))) as pool:
        futures = {pool.submit(_call, p, city, kw): (p.name, kw) for p, kw in jobs}
        for fut in as_completed(futures):
            try:
                raw.extend(fut.result())
            except httpx.HTTPError:
                continue  # 单源失败剔除,不影响其余

    # 名称归一化合并:同 key 记录命中的平台集合
    groups: dict[str, dict] = {}
    for p in raw:
        key = _norm(p.name, city)
        if not key:
            continue
        g = groups.setdefault(key, {"name": p.name, "sources": set(), "poi": p, "n": 0})
        g["sources"].add(p.sources[0] if p.sources else "?")
        # 优先保留有 url/image_url 的记录
        if p.url and not g["poi"].url:
            g["poi"].url = p.url
        if p.image_url and not g["poi"].image_url:
            g["poi"].image_url = p.image_url
        if p.ticket_price is not None and g["poi"].ticket_price is None:
            g["poi"] = p

    results = []
    for g in groups.values():
        poi = g["poi"]
        poi.sources = sorted(g["sources"])
        poi.verified = len(poi.sources) >= 2
        results.append(poi)
    results.sort(key=lambda x: (not x.verified, -(x.rating or 0), x.name))
    return results


def _call(provider: PoiProvider, city: str, kw: str) -> list[Poi]:
    return provider.search(city, kw)
