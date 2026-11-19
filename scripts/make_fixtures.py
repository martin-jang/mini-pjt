"""합성 변이 픽스처 + L2 정답 라벨 생성 스크립트 (T06, 결정 D12).

교육용 더미 데이터입니다. 실제 크롤링 스냅샷 화면을 복제해 '비슷하지만 미묘하게 다른' 변이를
의도적으로 주입한 가상의 레거시 시스템(fixture 도메인)을 만듭니다.

핵심: 정답 라벨은 사람이 분석 결과를 보고 쓰는 것이 아니라, 이 스크립트가 주입한 변이 목록에서
자동으로 만들어집니다. 그래서 정답이 분석 결과에 끌려가지 않습니다.

출력:
  data/fixtures/<FIXTURE_DOMAIN>/*.json    크롤러 스냅샷과 같은 형식의 화면들
  evaluation/golden/variant_groups.json    주입한 변이 그룹 (정답)
  evaluation/golden/unification_labels.json 그룹별 기대 결정 (통일 / 변형 유지 / 보류)
  evaluation/golden/screens.json           화면 목록 정답 (실제 업무 화면 + 픽스처 화면)
  evaluation/golden/fields.json            화면별 필드 정답

실행: python scripts/make_fixtures.py
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.crawler_core import load_snapshots  # noqa: E402

FIXTURE_DOMAIN = "legacy-fixture.example"
FIXTURE_DIR = ROOT / "data" / "fixtures" / FIXTURE_DOMAIN
GOLDEN_DIR = ROOT / "evaluation" / "golden"
NOTE = "교육용 더미 데이터입니다. 실제 시스템 화면이 아니라 변이를 주입한 합성 픽스처입니다."

# 업무 화면으로 볼 실제 스냅샷의 키워드 (관리·문서·뉴스 화면 제외). 픽스처 생성 대상 선택에만 사용.
BUSINESS_HINTS = ("overview", "activity", "findtrans", "transfer", "billpay", "openaccount",
                  "requestloan", "updateprofile", "transaction", "register", "lookup", "index")


def _find(snaps: list[dict], key: str) -> dict:
    for s in snaps:
        if key in s["screen_id"] and "__result" not in s["screen_id"]:
            return s
    raise SystemExit(f"스냅샷에서 '{key}' 화면을 찾지 못했습니다. 먼저 크롤링을 실행하세요.")


def _fixture(base: dict, sid: str, title: str) -> dict:
    s = copy.deepcopy(base)
    s.update(screen_id=sid, url=f"https://{FIXTURE_DOMAIN}/{sid}.jsp", url_pattern=f"//{FIXTURE_DOMAIN}/{sid}.jsp",
             title=title, fixture_note=NOTE, requires_login=True)
    s.pop("captured_at", None)
    return s


def _set_button(screen: dict, old_hint: str | None, new_label: str) -> None:
    """폼 버튼 라벨을 바꿉니다. old_hint가 없으면 첫 폼의 첫 버튼."""
    # 같은 라벨 버튼이 여러 폼에 반복될 수 있으므로(예: 검색 폼 여러 개) 일치하는 버튼을 모두 바꿉니다
    changed = False
    for f in screen.get("forms", []):
        for i, b in enumerate(f.get("buttons", [])):
            if old_hint is None or old_hint.lower() in b.lower():
                f["buttons"][i] = new_label
                changed = True
                if old_hint is None:
                    return
    if changed:
        return
    screen.setdefault("forms", [{"index": 0, "id": None, "action": None, "method": "GET", "fields": [],
                                 "buttons": []}])[0]["buttons"].append(new_label)


def _set_date_format(screen: dict, fmt: str) -> None:
    """거래 테이블 샘플 행의 날짜 표기를 바꿉니다 (예시 날짜 2025-12-11 기준)."""
    sample = {"MM-DD-YYYY": "12-11-2025", "YYYY/MM/DD": "2025/12/11", "YYYYMMDD": "20251211",
              "DD.MM.YYYY": "11.12.2025"}[fmt]
    for t in screen.get("tables", []):
        if any("date" in h.lower() for h in t.get("headers", [])):
            col = next(i for i, h in enumerate(t["headers"]) if "date" in h.lower())
            t["sample_rows"] = [[sample if j == col else c for j, c in enumerate(r)] for r in t["sample_rows"]] or [[sample]]
            t["date_format"] = fmt


def main() -> None:
    snaps = [s for s in load_snapshots() if not s["screen_id"].startswith("legacy_fixture")]
    overview, activity = _find(snaps, "overview"), _find(snaps, "activity")
    findtrans, transfer, billpay = _find(snaps, "findtrans"), _find(snaps, "transfer"), _find(snaps, "billpay")

    screens: list[dict] = []
    groups: list[dict] = []
    labels: list[dict] = []

    # ── 화면 정의 ────────────────────────────────────────────
    # 계좌 목록 2종: 헤더 라벨 변이 + 합계 행 유무(업무 의미 있는 차이)
    acc_a = _fixture(overview, "fx_account_list_a", "계좌 목록 A")
    acc_b = _fixture(overview, "fx_account_list_b", "계좌 조회 B")
    acc_b["tables"][0]["headers"] = ["Acct No", "Balance", "Avail. Amt"]
    acc_a["tables"][0]["has_total_row"] = True
    acc_b["tables"][0]["has_total_row"] = False

    # 거래내역 3종: 검색 버튼 라벨 변이 + 날짜 형식 변이 + 조회조건 위치 변이
    act_a = _fixture(activity, "fx_activity_a", "거래내역 A")
    act_b = _fixture(activity, "fx_activity_b", "거래내역 조회 B")
    act_c = _fixture(findtrans, "fx_activity_c", "거래 검색 C")
    _set_button(act_a, "go", "Go")
    _set_button(act_b, "go", "Search")
    _set_button(act_c, "find", "조회")
    _set_date_format(act_a, "MM-DD-YYYY")
    _set_date_format(act_b, "YYYY/MM/DD")
    _set_date_format(act_c, "YYYYMMDD")
    act_a["layout"] = {"search_panel": "top"}
    act_b["layout"] = {"search_panel": "left"}
    act_c["layout"] = {"search_panel": "top"}

    # 송금 2종: 확인 단계 유무(업무 의미 → 변형 유지), 제출 버튼 라벨 변이
    tr_a = _fixture(transfer, "fx_transfer_a", "이체 A")
    pay_b = _fixture(billpay, "fx_payment_b", "납부 B")
    tr_a["flow"] = {"confirm_step": True}
    pay_b["flow"] = {"confirm_step": False}
    _set_button(tr_a, "transfer", "Transfer")
    _set_button(pay_b, "send", "Submit")

    screens = [acc_a, acc_b, act_a, act_b, act_c, tr_a, pay_b]

    # ── 주입한 변이 = 정답 ───────────────────────────────────
    def group(gid, role, members, decision, standard, reason):
        groups.append({"group_id": gid, "role": role, "members": members})
        labels.append({"group_id": gid, "expected_decision": decision, "expected_standard": standard,
                       "reason": reason})

    group("G1_search_action", "검색 실행 버튼",
          [{"screen_id": "fx_activity_a", "value": "Go"}, {"screen_id": "fx_activity_b", "value": "Search"},
           {"screen_id": "fx_activity_c", "value": "조회"}],
          "unify", None, "의미가 같고 라벨 표기만 다름")
    group("G2_date_format", "날짜 표기 형식",
          [{"screen_id": "fx_activity_a", "value": "MM-DD-YYYY"}, {"screen_id": "fx_activity_b", "value": "YYYY/MM/DD"},
           {"screen_id": "fx_activity_c", "value": "YYYYMMDD"}],
          "unify", "YYYY-MM-DD", "형식만 다름 → 표준 ISO 형식으로 통일")
    group("G3_account_headers", "계좌 목록 컬럼 라벨",
          [{"screen_id": "fx_account_list_a", "value": "Account / Balance* / Available Amount"},
           {"screen_id": "fx_account_list_b", "value": "Acct No / Balance / Avail. Amt"}],
          "unify", None, "같은 컬럼의 라벨 표기만 다름")
    group("G4_search_panel_layout", "조회조건 영역 위치",
          [{"screen_id": "fx_activity_a", "value": "top"}, {"screen_id": "fx_activity_b", "value": "left"},
           {"screen_id": "fx_activity_c", "value": "top"}],
          "unify", "top", "배치만 다름 → 다수결(top)")
    group("G5_total_row", "목록 합계 행",
          [{"screen_id": "fx_account_list_a", "value": True}, {"screen_id": "fx_account_list_b", "value": False}],
          "keep_variant", None, "합계 행 유무는 업무 정보 차이 → 공통 컴포넌트 옵션(prop)으로 유지")
    group("G6_confirm_step", "제출 전 확인 단계",
          [{"screen_id": "fx_transfer_a", "value": True}, {"screen_id": "fx_payment_b", "value": False}],
          "keep_variant", None, "확인 단계는 동작 차이 → 자동 통일 금지 (과잉 통일 방지)")

    # ── 저장 ───────────────────────────────────────────────
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    for old in FIXTURE_DIR.glob("*.json"):
        old.unlink()
    for s in screens:
        (FIXTURE_DIR / f"{s['screen_id']}.json").write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")

    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    business = [s for s in snaps if any(h in s["screen_id"] for h in BUSINESS_HINTS) and "api_docs" not in s["screen_id"]]
    golden_screens = {
        "note": "화면 목록 정답. real = 크롤링된 업무 화면, fixture = 합성 픽스처 화면",
        "real": sorted(s["screen_id"] for s in business),
        "fixture": [s["screen_id"] for s in screens],
    }
    golden_fields = {s["screen_id"]: sorted({f["name"] for fm in s.get("forms", []) for f in fm["fields"] if f["name"]})
                     for s in business + screens}
    dump = lambda name, obj: (GOLDEN_DIR / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    dump("variant_groups.json", {"note": NOTE, "groups": groups})
    dump("unification_labels.json", {"note": NOTE, "labels": labels})
    dump("screens.json", golden_screens)
    dump("fields.json", golden_fields)
    print(f"픽스처 화면 {len(screens)}개, 변이 그룹 {len(groups)}개 "
          f"(변형 유지 {sum(l['expected_decision'] == 'keep_variant' for l in labels)}개), "
          f"정답 업무 화면 {len(golden_screens['real'])}개")


if __name__ == "__main__":
    main()
