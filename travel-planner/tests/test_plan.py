"""端到端与单元测试。CI/本地均无 ANTHROPIC_API_KEY → 自动走确定性演示模式。

覆盖 specs:意图解析、多源检索去重、无凭证兜底、预算不足提示、价格快照。
"""

from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import costing, llm, model_runtime, poi
from app.main import app
from app.models import Poi, TripRequest
from app.retrieval import search_all
from app.store import connect, record_snapshot
from app.suppliers import resolve_suppliers
from app.suppliers.mock import MockAdapter
from app.suppliers.tuniu import TuniuAdapter

client = TestClient(app)


@pytest.fixture(autouse=True)
def _force_demo_mode(monkeypatch, tmp_path):
    """保证走确定性演示模式,测试不依赖真实 LLM/POI 网络调用。"""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("TUNIU_API_KEY", raising=False)
    monkeypatch.delenv("AMAP_KEY", raising=False)
    monkeypatch.delenv("TENCENT_MAP_KEY", raising=False)
    monkeypatch.delenv("BAIDU_MAP_KEY", raising=False)
    monkeypatch.delenv("PLANNER_PROVIDER", raising=False)
    monkeypatch.delenv("PLANNER_PARSE_MODEL", raising=False)
    monkeypatch.delenv("PLANNER_PLAN_MODEL", raising=False)
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.setenv("PLANNER_DB_PATH", str(tmp_path / "test.db"))  # 隔离会话/快照写入
    model_runtime.reset()  # 忽略持久化文件,回到环境默认(未配置)


def _sample_request() -> TripRequest:
    return TripRequest(
        origin="上海",
        destinations=["西安"],
        days=5,
        adults=1,
        elders=1,
        per_person_budget=3000.0,
        preferences=["人文"],
    )


class TestEndToEnd:
    def test_healthz(self):
        resp = client.get("/healthz")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        assert resp.json()["llm_configured"] is False

    def test_plan_happy_path(self):
        resp = client.post(
            "/api/plan", json={"text": "上海出发带老人去西安5天人均3000偏人文"}
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["is_mock"] is True
        assert "mock" in body["sources"]
        assert body["recorded_snapshot"] is True
        assert body["budget_status"] in {"ok", "over_budget"}
        assert len(body["recommendations"]) >= 1
        assert body["per_person_estimate"] > 0
        # 新能力:逐日路线、多平台景点、费用分解、实时资讯默认关
        assert len(body["days"]) == 5
        assert body["pois"]
        assert body["cost_breakdown"]["total"] > 0
        assert body["web_research_used"] is False

    def test_web_page_served(self):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "旅行规划" in resp.text

    def test_plan_budget_over_flagged(self):
        resp = client.post("/api/plan", json={"text": "上海去北京8天人均800"})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["budget_status"] == "over_budget"
        assert "超出" in body["note"]

    def test_plan_missing_destination_422(self):
        resp = client.post("/api/plan", json={"text": "帮我随便规划一次旅行"})
        assert resp.status_code == 422
        assert "目的地" in resp.json()["detail"]["missing_fields"]


class TestSuppliersAndStore:
    def test_resolve_falls_back_to_mock_without_tuniu_credentials(self):
        suppliers = resolve_suppliers(enable_tuniu=True)
        assert [s.name for s in suppliers] == ["mock"]

    def test_mock_is_deterministic_for_same_query(self):
        a = search_all(_sample_request(), [MockAdapter()])
        b = search_all(_sample_request(), [MockAdapter()])
        # 忽略逐次不同的采集时间戳,比较去重键与价格
        key_a = sorted((q.operator, q.price) for q in a.transport)
        key_b = sorted((q.operator, q.price) for q in b.transport)
        assert key_a == key_b
        assert [h.name for h in a.hotels] == [h.name for h in b.hotels]
        assert a.is_mock is True

    def test_dedup_keeps_lowest_price_when_multiple_sources(self):
        bundle = search_all(_sample_request(), [MockAdapter(), MockAdapter()])
        keys = [q.dedup_key for q in bundle.transport]
        assert len(keys) == len(set(keys))  # 无重复 key
        assert all("+" in q.supplier for q in bundle.transport)  # 多源已合并

    def test_snapshot_records_rows(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PLANNER_DB_PATH", str(tmp_path / "t.db"))
        request = _sample_request()
        bundle = search_all(request, [MockAdapter()])
        rows = record_snapshot(request, bundle)
        assert rows == len(bundle.transport) + len(bundle.hotels)
        with connect() as conn:
            count = conn.execute("SELECT COUNT(*) FROM price_snapshots").fetchone()[0]
        assert count == rows


class TestItinerary:
    def _fake_provider(self, name, poi_name):
        class _P(poi.PoiProvider):
            def search(self, city, query, client=None):
                return [Poi(name=poi_name, sources=[name])]

        _P.name = name
        return _P()

    def test_poi_cross_verified_when_two_providers(self):
        res = poi.search_pois(
            "西安",
            ["景点"],
            [self._fake_provider("高德", "西安大雁塔"), self._fake_provider("腾讯", "大雁塔")],
        )
        assert any(p.verified and set(p.sources) == {"高德", "腾讯"} for p in res)

    def test_poi_single_provider_not_verified(self):
        res = poi.search_pois("西安", ["景点"], [self._fake_provider("高德", "西安大雁塔")])
        assert res and all(p.verified is False for p in res)

    def test_mock_poi_for_known_city(self):
        res = poi.MockPoiProvider().search("西安", "景点")
        assert res
        assert all(p.is_mock for p in res)
        assert res[0].ticket_price is not None
        # 新能力:mock 景点也有地图链接
        assert all(p.url is not None for p in res)
        assert "uri.amap.com" in res[0].url

    def test_poi_url_image_propagated_in_plan(self):
        """验证 POI 的 url/image_url 字段在规划响应中正确传递。"""
        resp = client.post(
            "/api/plan", json={"text": "上海出发带老人去西安5天人均3000偏人文"}
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        for p in body["pois"]:
            assert "url" in p, "POI 应包含 url 字段"
            assert "image_url" in p, "POI 应包含 image_url 字段"

    def test_cost_is_deterministic(self):
        request = _sample_request()
        bundle = search_all(request, [MockAdapter()])
        pois = poi.MockPoiProvider().search("西安", "景点")
        cost = costing.estimate_cost(request, bundle, pois, nights=4)
        travelers = request.adults + request.elders + request.children
        assert cost.total == cost.transport + cost.hotels + cost.tickets + cost.meals
        assert cost.per_person == round(cost.total / travelers, 1)
        assert cost.meals == (request.days or 1) * travelers * costing.MEAL_RATE


class TestLocalTour:
    def test_parse_local_tour_demo(self):
        req = llm.parse_intent("苏州出发国庆带娃去周边自驾6天")
        assert req.origin == "苏州"
        assert req.destinations == ["苏州"]
        assert req.local_tour is True
        assert req.days == 6
        assert "亲子" in req.preferences

    def test_plan_local_tour_without_destination(self):
        resp = client.post(
            "/api/plan", json={"text": "苏州出发国庆带娃去周边自驾6天"}
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert len(body["days"]) == 6
        assert body["cost_breakdown"]["transport"] == 0.0
        assert all(r["kind"] != "transport" for r in body["recommendations"])
        assert body["pois"]


class TestTransportFixed:
    """用户已自行安排跨城交通(已购机票/已定航班)时,不得再推荐/安排交通。"""

    def test_parse_transport_fixed_heuristic(self):
        req = llm.parse_intent("无锡出发坐飞机去贵州7天,机票已买好")
        assert req.transport_fixed is True
        # 仅说坐飞机、未说已买票 → 不算固定
        req2 = llm.parse_intent("无锡出发坐飞机去贵州7天")
        assert req2.transport_fixed is False

    def test_parse_fixed_cost_from_feedback(self):
        req = llm.parse_feedback(
            TripRequest(origin="无锡", destinations=["贵州"], days=7),
            "我是要坐飞机去,两个人价格是4400,不用再计算了",
        )
        assert req.transport_fixed is True
        assert req.fixed_transport_cost == 4400.0

    def test_transport_fixed_no_transport_in_plan(self):
        resp = client.post(
            "/api/plan",
            json={"text": "无锡出发去贵阳7天,航班已订好,两个人机票4400不用算了"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        # 推荐里没有比价型交通方案;若有也是「已自订」占位,不含真实车次
        for r in body["recommendations"]:
            if r["kind"] == "transport":
                assert r["supplier"] == "自行安排"
                assert r["price"] == 4400.0
        # 费用把 4400 计入
        assert body["cost_breakdown"]["transport"] == 4400.0
        # 首日不写「乘 Mock…抵达」
        first = body["days"][0]["activities"][0]
        assert "按已定的交通" in first["title"] or "已定" in first["title"]

    def test_transport_fixed_without_cost_zero_transport(self):
        resp = client.post(
            "/api/plan", json={"text": "无锡出发去贵阳7天,我已经买了机票不用安排交通"}
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["cost_breakdown"]["transport"] == 0.0
        assert all(r["kind"] != "transport" for r in body["recommendations"])

    def test_refine_applies_transport_fixed(self):
        """先出普通计划,再反馈「坐飞机不用算交通」→ 新计划不再推荐交通。"""
        first = client.post(
            "/api/plan", json={"text": "上海出发去西安5天人均3000偏人文"}
        ).json()
        sid = first["session_id"]
        resp = client.post(
            f"/api/plan/{sid}/refine",
            json={"feedback": "我是坐飞机去的,机票已买,往返4400不用再算交通"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["cost_breakdown"]["transport"] == 4400.0
        for r in body["recommendations"]:
            if r["kind"] == "transport":
                assert "Mock" not in r["label"]  # 不再是比价推荐

    def test_refine_extracts_cost_with_long_separator(self):
        """真实句式:金额与「机票」之间隔了较长的修饰短语,也应提取到总价。"""
        first = client.post(
            "/api/plan", json={"text": "无锡出发去贵阳7天"}
        ).json()
        sid = first["session_id"]
        resp = client.post(
            f"/api/plan/{sid}/refine",
            json={"feedback": "我机票已经买好了,两个人4400,不用再算了"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["cost_breakdown"]["transport"] == 4400.0
        # 交通推荐退化为「已自订」占位而非比价方案
        transports = [r for r in body["recommendations"] if r["kind"] == "transport"]
        assert transports and transports[0]["supplier"] == "自行安排"
        assert "按已定的交通" in body["days"][0]["activities"][0]["title"]


class TestModelConfig:
    def test_config_endpoints_roundtrip(self, monkeypatch, tmp_path):
        monkeypatch.setenv("MODEL_CONFIG_PATH", str(tmp_path / "mc.json"))
        got = client.get("/api/config/model").json()
        assert got["configured"] is False

        set_r = client.post(
            "/api/config/model",
            json={"api_key": "sk-ant-fakelongkey12345678", "parse_model": "claude-haiku-4-5"},
        )
        assert set_r.status_code == 200
        info = set_r.json()
        assert info["configured"] is True
        assert "sk-ant-fakelongkey12345678" not in json.dumps(info, ensure_ascii=False)
        assert info["api_key_masked"]

        # 空串清除
        clear = client.post("/api/config/model", json={"api_key": ""}).json()
        assert clear["configured"] is False

    def test_provider_roundtrip_and_defaults(self, monkeypatch, tmp_path):
        monkeypatch.setenv("MODEL_CONFIG_PATH", str(tmp_path / "mc.json"))
        model_runtime.reset()
        assert model_runtime.provider() == "anthropic"
        assert model_runtime.parse_model() == "claude-haiku-4-5"
        assert model_runtime.plan_model() == "claude-sonnet-5"

        set_r = client.post(
            "/api/config/model",
            json={"api_key": "sk-fakelongkey12345678", "provider": "openai"},
        )
        assert set_r.status_code == 200
        info = set_r.json()
        assert info["provider"] == "openai"
        assert info["parse_model"] == "deepseek-chat"
        assert info["plan_model"] == "deepseek-chat"

        # 显式指定模型优先
        set_r2 = client.post(
            "/api/config/model",
            json={"provider": "openai", "plan_model": "deepseek-reasoner"},
        )
        assert set_r2.json()["plan_model"] == "deepseek-reasoner"

        # 清空全部,回到 anthropic 默认
        clear = client.post(
            "/api/config/model",
            json={"provider": "", "api_key": "", "parse_model": "", "plan_model": ""},
        ).json()
        assert clear["provider"] == "anthropic"
        assert clear["parse_model"] == "claude-haiku-4-5"
        assert clear["plan_model"] == "claude-sonnet-5"

    def test_openai_parse_json_mode(self, monkeypatch, tmp_path):
        monkeypatch.setenv("MODEL_CONFIG_PATH", str(tmp_path / "mc.json"))
        model_runtime.reset()
        model_runtime.set_config(
            api_key="sk-test", provider="openai", base_url="https://api.deepseek.com"
        )

        class _FakeResp:
            status_code = 200
            text = ""

            def json(self):
                return {"choices": [{"message": {"content": json.dumps(
                    {"origin": "上海", "destinations": ["西安"], "days": 5, "adults": 1,
                     "elders": 0, "children": 0, "preferences": ["人文"], "local_tour": False}
                )}}]}

        captured = {}

        def _fake_post(url, **kwargs):
            captured["url"] = url
            captured["payload"] = kwargs.get("json")
            return _FakeResp()

        monkeypatch.setattr("app.llm.httpx.post", _fake_post)
        req = llm.parse_intent("上海去西安5天")
        assert isinstance(req, TripRequest)
        assert req.origin == "上海"
        assert req.destinations == ["西安"]
        assert captured["url"] == "https://api.deepseek.com/chat/completions"
        assert captured["payload"]["model"] == "deepseek-chat"
        assert captured["payload"]["response_format"] == {"type": "json_object"}

    def test_gather_live_info_disabled_for_openai(self, monkeypatch, tmp_path):
        monkeypatch.setenv("MODEL_CONFIG_PATH", str(tmp_path / "mc.json"))
        model_runtime.reset()
        model_runtime.set_config(api_key="sk-test", provider="openai")
        pois = [Poi(name="测试景点", sources=["mock"])]
        assert llm.gather_live_info(pois, enabled=True) == ""

    def test_effective_base_url_normalizes_platform(self, monkeypatch, tmp_path):
        monkeypatch.setenv("MODEL_CONFIG_PATH", str(tmp_path / "mc.json"))
        model_runtime.reset()
        # 未配置 base_url → 默认 api.deepseek.com
        model_runtime.set_config(api_key="sk-test", provider="openai")
        assert model_runtime.effective_base_url() == "https://api.deepseek.com"
        # 误填网页控制台 → 纠正为 api.deepseek.com
        model_runtime.set_config(base_url="https://platform.deepseek.com")
        assert model_runtime.effective_base_url() == "https://api.deepseek.com"


class _FakeResp:
    status_code = 200

    def __init__(self, text: str) -> None:
        self.text = text


def _mcp_env(business: dict) -> str:
    inner = json.dumps(business, ensure_ascii=False)
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {"content": [{"type": "text", "text": inner}]},
    }
    return json.dumps(payload, ensure_ascii=False)


class TestTuniuAdapter:
    def test_transport_mapping_train_and_flight(self, monkeypatch):
        monkeypatch.setenv("TUNIU_API_KEY", "sk-test")
        train = {"data": [{
            "trainNum": "G203", "departStationName": "张家港", "destStationName": "贵阳北",
            "departureTime": "2026-09-29 07:30", "arrivalTime": "2026-09-29 15:14",
            "price": {"edzPrice": "943", "ydzPrice": "1496", "swzPrice": "3292"},
        }]}
        flight = {"data": [{
            "flightNumber": "AQ1332", "departureAirport": "硕放", "departureTerminal": "T2",
            "arrivalAirport": "龙洞堡", "arrivalTerminal": "T2",
            "departureTime": "2026-09-29 17:00", "arrivalTime": "2026-09-29 19:40",
            "basePrice": "799", "totalTax": "120", "cabinClass": "经济舱",
        }]}

        def _fake_post(url, **kwargs):
            text = _mcp_env(train) if "/train" in url else _mcp_env(flight)
            return _FakeResp(text)

        monkeypatch.setattr("app.suppliers.tuniu.httpx.post", _fake_post)
        q = SimpleNamespace(
            origin="苏州", destination="贵阳", travel_date=date(2026, 9, 29), travelers=2
        )
        quotes = TuniuAdapter().search_transport(q)
        assert {x.mode for x in quotes} == {"train", "flight"}

        t = next(x for x in quotes if x.mode == "train")
        assert t.operator == "G203"
        assert t.price == 943.0
        assert t.travel_class == "二等座"
        assert t.departure_station == "张家港"
        assert t.arrival_station == "贵阳北"
        assert t.departure_time == "07:30"

        f = next(x for x in quotes if x.mode == "flight")
        assert f.operator == "AQ1332"
        assert f.price == 919.0  # basePrice + totalTax
        assert f.travel_class == "经济舱"
        assert f.departure_station == "硕放T2"

    def test_hotel_mapping(self, monkeypatch):
        monkeypatch.setenv("TUNIU_API_KEY", "sk-test")
        hotel = {"hotels": [{
            "hotelName": "希岸·轻雅酒店", "roomName": "高级大床房", "lowestPrice": 377,
            "commentScore": 5, "refund": "限时取消",
        }]}

        def _fake_post(url, **kwargs):
            return _FakeResp(_mcp_env(hotel))

        monkeypatch.setattr("app.suppliers.tuniu.httpx.post", _fake_post)
        q = SimpleNamespace(city="贵阳", check_in=date(2026, 9, 29), nights=6, travelers=2)
        quotes = TuniuAdapter().search_hotel(q)
        assert len(quotes) == 1
        h = quotes[0]
        assert h.name == "希岸·轻雅酒店"
        assert h.room_type == "高级大床房"
        assert h.price_per_night == 377.0
        assert h.rating == 5.0
        assert h.is_refundable is True

    def test_resolve_suppliers_uses_tuniu_when_key(self, monkeypatch):
        monkeypatch.setenv("TUNIU_API_KEY", "sk-test")
        assert [s.name for s in resolve_suppliers()] == ["tuniu"]

    def test_resolve_suppliers_falls_back_to_mock_without_key(self):
        assert [s.name for s in resolve_suppliers()] == ["mock"]


def test_clamp_start_date_rolls_past_forward():
    from app.llm import _clamp_start_date

    req = TripRequest(origin="苏州", destinations=["贵阳"], start_date=date(2023, 9, 29))
    out = _clamp_start_date(req)
    assert out.start_date >= date.today()
    assert (out.start_date.month, out.start_date.day) == (9, 29)


class TestSessions:
    def test_session_roundtrip(self, monkeypatch, tmp_path):
        from app import sessions

        monkeypatch.setenv("PLANNER_DB_PATH", str(tmp_path / "s.db"))
        req = TripRequest(origin="上海", destinations=["西安"], days=5)
        bundle = search_all(req, [MockAdapter()])
        state = sessions.PlanState(request=req, bundle=bundle)
        sid = sessions.create(state)
        assert state.plan is None or state.plan.session_id is None
        got = sessions.get(sid)
        assert got is not None
        assert got.request.origin == "上海"
        assert got.bundle.transport


class TestRefine:
    def test_plan_returns_session_id(self):
        resp = client.post("/api/plan", json={"text": "上海出发带老人去西安5天人均3000偏人文"})
        assert resp.status_code == 200, resp.text
        assert resp.json()["session_id"]

    def test_refine_history_contains_snapshot(self):
        """refine 后 history 条目包含完整快照，可用于回退。"""
        from app import sessions

        first = client.post(
            "/api/plan", json={"text": "上海出发带老人去西安5天人均3000偏人文"}
        ).json()
        sid = first["session_id"]
        resp = client.post(f"/api/plan/{sid}/refine", json={"feedback": "预算降到100"})
        assert resp.status_code == 200, resp.text
        state = sessions.get(sid)
        assert len(state.history) == 1
        entry = state.history[0]
        assert entry.feedback == "预算降到100"
        assert entry.snapshot is not None
        assert entry.snapshot["budget_status"] == "over_budget"
        assert entry.snapshot["session_id"] == sid

    def test_get_sessions_lists_all(self):
        """GET /api/sessions 返回所有未过期会话。"""
        client.post("/api/plan", json={"text": "上海去西安5天"})
        resp = client.get("/api/sessions")
        assert resp.status_code == 200
        sessions = resp.json()
        assert len(sessions) >= 1
        s = sessions[0]
        assert "session_id" in s
        assert "request_summary" in s
        assert "history_count" in s
        assert "created_at" in s
        assert "updated_at" in s

    def test_session_expiry(self, monkeypatch, tmp_path):
        """过期会话返回 404。"""
        from datetime import datetime, timedelta, timezone
        from app import sessions as sess

        monkeypatch.setenv("PLANNER_DB_PATH", str(tmp_path / "e.db"))
        req = TripRequest(origin="上海", destinations=["西安"], days=5)
        bundle = search_all(req, [MockAdapter()])
        state = sess.PlanState(request=req, bundle=bundle)
        # 手动设为已过期
        state.expires_at = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(timespec="seconds")
        sid = sess.create(state)
        resp = client.get(f"/api/plan/{sid}")
        assert resp.status_code == 404

    def test_multi_refine_preserves_snapshots(self):
        """多次 refine 后每个历史版本的快照都可用，可按版本回退。"""
        from app import sessions

        first = client.post(
            "/api/plan", json={"text": "上海出发带老人去西安5天人均3000偏人文"}
        ).json()
        sid = first["session_id"]
        # 第一次 refine: 预算降到 100
        r1 = client.post(f"/api/plan/{sid}/refine", json={"feedback": "预算降到100"})
        assert r1.status_code == 200
        # 第二次 refine: 改成 7 天
        r2 = client.post(f"/api/plan/{sid}/refine", json={"feedback": "改成7天"})
        assert r2.status_code == 200
        assert len(r2.json()["days"]) == 7

        state = sessions.get(sid)
        assert len(state.history) == 2
        # 第 1 版快照：5 天、预算 100
        snap1 = state.history[0].snapshot
        assert snap1["budget_status"] == "over_budget"
        # 第 2 版快照：7 天
        snap2 = state.history[1].snapshot
        assert len(snap2["days"]) == 7

    def test_refine_unknown_session_404(self):
        first = client.post(
            "/api/plan", json={"text": "上海出发带老人去西安5天人均3000偏人文"}
        ).json()
        sid = first["session_id"]
        resp = client.post(f"/api/plan/{sid}/refine", json={"feedback": "预算降到100"})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["session_id"] == sid
        assert body["budget_status"] == "over_budget"

    def test_refine_changes_days(self):
        first = client.post(
            "/api/plan", json={"text": "上海出发带老人去西安5天人均3000偏人文"}
        ).json()
        sid = first["session_id"]
        body = client.post(f"/api/plan/{sid}/refine", json={"feedback": "改成7天"}).json()
        assert len(body["days"]) == 7

    def test_refine_unknown_session_404(self):
        resp = client.post("/api/plan/nonexistent/refine", json={"feedback": "x"})
        assert resp.status_code == 404

    def test_get_session_returns_plan(self):
        first = client.post(
            "/api/plan", json={"text": "上海出发带老人去西安5天人均3000偏人文"}
        ).json()
        sid = first["session_id"]
        resp = client.get(f"/api/plan/{sid}")
        assert resp.status_code == 200
        assert resp.json()["session_id"] == sid

    def test_structured_activities(self):
        body = client.post(
            "/api/plan", json={"text": "上海出发带老人去西安5天人均3000偏人文"}
        ).json()
        for day in body["days"]:
            for a in day["activities"]:
                assert "title" in a
                assert isinstance(a["kind"], str)
