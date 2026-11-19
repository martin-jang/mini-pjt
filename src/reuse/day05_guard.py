"""Day 5 가드레일 재사용 (sds-ax-training/day05/practice/starter/submission.py 에서 복사).

제출 저장소가 다른 저장소 경로에 의존하지 않도록 input_guard·mask_pii 부분만 복사해 둡니다.
원본 규칙은 수정하지 않고, 이 프로젝트에 필요한 보강은 src/guardrails.py 에서 합니다.
"""

from __future__ import annotations

import re

# ══════════════════════════════════════════════════════════════════
# 기초 파트 (7점)
# ══════════════════════════════════════════════════════════════════

# ------------------------------------------------------------------
# 입력 가드 규칙
#
# 설계 원칙: "단어 하나"가 아니라 "의도의 조합"을 봅니다.
#   - "이전", "무시", "관리자", "새로운 역할"은 정상 문장에도 흔히 나옵니다.
#   - 공격은 [덮어쓰는 동작] + [현재 지시라는 대상]이 함께 나오거나,
#     [내부 정보라는 대상] + [드러내라는 동작]이 함께 나올 때입니다.
# 각 규칙은 (사유, 정규식) 쌍이며 위에서부터 차례로 검사합니다.
# 정규식 사이 간격은 .{0,N}처럼 길이를 제한해 아주 긴 입력에서도 빠르게 끝나게 합니다.
# ------------------------------------------------------------------

# 덮어쓰기의 "범위" — 어떤 지시를 가리키는가 (이전 것, 위의 것, 전부)
_SCOPE = r"(이전|지난|앞서|앞의|앞에|위의|위에|위|기존|원래|처음|초기|지금까지|여태|그동안|모든|전부|기본)"
# 덮어쓰기의 "대상" — 모델이 따르는 지시 자체
#   "설정"은 넣지 않습니다. "기존 설정 초기화해줘"는 정상 운영 요청입니다.
_TARGET = r"(지시|명령|규칙|룰|프롬프트|지침|제약|대화|맥락|컨텍스트|instruction|prompt|rule)"
# 덮어쓰는 "동작" — 무효화하려는 의도
#   "취소·리셋·초기화"는 넣지 않습니다. "이전 명령 취소해줘"는 운영에서 흔한 정상 요청입니다.
_OVERRIDE = (
    r"(무시|잊|잊어|버리|버려|됐고|됐어|되었고|필요\s*없|상관\s*없|신경\s*쓰지|따르지|무효|폐기)"
)
# 무효화 동작 뒤에 이런 꼬리가 붙으면 "그래도 되는지 묻는" 정상 질문이거나 과거 서술입니다.
#   예) "위 알람 규칙은 무시해도 되나요?", "지난 대화 내용을 잊어버렸는데"
_NOT_COMMAND = (
    r"(?!.{0,3}(렸|었|았|도\s*(되|돼|괜찮)|면\s*(되|돼)|야\s*(하|돼|되)|할\s*수|는\s*(법|방법|기준|경우|게|지)))"
)

# 내부 지침(시스템 프롬프트) — 운영 어시스턴트에게 이걸 보여 달라는 정상 요청은 없습니다
_SYSTEM_PROMPT = (
    r"(시스템\s*프롬프트|시스템\s*메시지|시스템\s*지침|시스템\s*지시|시스템\s*설정\s*문|"
    r"system\s*(prompt|message|instruction)s?|내부\s*지침|숨겨진\s*(지시|지침|프롬프트|규칙)|"
    r"초기\s*(지시|프롬프트|지침)|원래\s*(지시문|프롬프트)|너의\s*(지시|지침|프롬프트)|"
    r"당신의\s*(지시|지침|프롬프트)|your\s*(prompt|instructions?|rules|guidelines))"
)
_REVEAL = (
    r"(출력|알려|보여|공개|노출|말해|읊|적어|써\s*줘|복사|붙여|전문|그대로|원문|인코딩|"
    r"번역|요약|reveal|print|show|tell|display|dump|repeat|leak|encode|what)"
)
# 비밀값 — 바로 뒤(조사 정도만 사이)에 드러내는 동작이 올 때만 차단합니다.
#   "토큰 만료 시간 알려줘"처럼 사이에 다른 명사가 끼면 정상 문의로 봅니다.
_SECRET = (
    r"(비밀\s*번호|패스워드|password|암호|토큰|token|api\s*키|api\s*key|액세스\s*키|access\s*key|"
    r"시크릿|secret|자격\s*증명|credential|private\s*key|개인\s*키|인증\s*키)"
)

# 대량 파괴 명령에서 "운영 자원"으로 보는 대상
_RESOURCE = r"(db|데이터베이스|database|테이블|table|자산|서버|데이터|백업|로그|클러스터|버킷|인스턴스)"

_RULES: list[tuple[str, re.Pattern[str]]] = [
    # 1) 지시 덮어쓰기 — 한국어: [범위] + [대상] + [무효화 동작]
    (
        "지시 덮어쓰기 시도 (이전 지시 무효화)",
        re.compile(_SCOPE + r".{0,12}" + _TARGET + r".{0,12}" + _OVERRIDE + _NOT_COMMAND),
    ),
    # 1-2) 영어: ignore/disregard/forget ... previous/all ... instructions
    (
        "지시 덮어쓰기 시도 (영문)",
        re.compile(
            r"(ignore|disregard|forget|override|bypass|skip)\s.{0,30}"
            r"(previous|prior|above|earlier|all|any|your|the|system)\s.{0,20}"
            r"(instructions?|prompts?|rules|guidelines|directions|context)"
        ),
    ),
    # 2) 역할 탈취 — 모델에게 새 정체성을 "부여"하려는 시도
    #   "너의 역할은 뭐야?"처럼 묻는 문장은 통과시키고, 지금부터/이제 + 새 역할을 정해 주는 문장만 막습니다.
    #   "새로운 역할 담당자가 배정되었는지"처럼 사람의 역할을 묻는 문장도 통과합니다.
    (
        "역할 탈취 시도 (새 역할 부여)",
        re.compile(
            r"((지금부터|이제부터|오늘부터|앞으로는?)\s*.{0,6}(너|당신|넌)(의|는|은)?\s*.{0,6}(역할|정체|임무|이름|페르소나)|"
            r"(너|당신|넌)(는|은)?\s*이제\s*(부터)?\s*[^?？]{0,20}(이다|이야|입니다|야)(\s|[.!]|$)|"
            r"(너|당신)(의|에게)?\s*(새로운|새)\s*(역할|임무|정체|페르소나)|"
            r"(새로운|새|다른)\s*(역할|페르소나|인격|정체성)(을|를)\s*(부여|맡|수행|가져|받)|"
            r"역할(을|를)\s*부여\s*받|"
            r"you\s+are\s+(now|no\s+longer)|act\s+as\s+(an?\s+)?(unrestricted|unfiltered|different|new|evil)|"
            r"pretend\s+(to\s+be|you\s+are)|\bdan\b|do\s+anything\s+now|jailbreak|탈옥)"
        ),
    ),
    # 2-2) 권한 모드 전환 — 관리자/개발자/탈옥 모드는 모델 자신에 대한 권한 상승 요구입니다
    (
        "권한 모드 전환 시도",
        re.compile(
            r"(관리자|개발자|운영자|루트|무제한|제한\s*없는|필터\s*없는|god|admin|developer|root|sudo|unrestricted)"
            r"\s*(모드|mode)\s*(로|으로)?\s*(전환|진입|변경|활성|켜|on|들어가|이야|야|다|입니다|enabled|activated)"
        ),
    ),
    # 2-3) "지금부터 ~모드야" — 모델의 동작 모드를 대화로 바꾸려는 시도 (점검/디버그 모드 등)
    #   "payment-api를 점검 모드로 전환해줘" 같은 서비스 조작 요청은 "지금부터/이제부터"가 없으므로 통과합니다.
    (
        "동작 모드 변경 시도",
        re.compile(r"(지금부터|이제부터|이제는)\s*.{0,10}(모드|mode)\s*(야|다|이야|입니다|로\s*동작|로\s*전환|로\s*답)"),
    ),
    # 3) 내부 지침 유출 — [시스템 프롬프트류 대상] + [드러내는 동작]
    (
        "내부 지침 유출 시도",
        re.compile(
            _SYSTEM_PROMPT + r".{0,20}" + _REVEAL + r"|" + _REVEAL + r".{0,20}" + _SYSTEM_PROMPT
        ),
    ),
    # 3-2) 비밀값 유출 — [비밀값] 바로 뒤에 [드러내는 동작]
    #   "노출"은 넣지 않습니다. "API 키가 노출됐어요"는 막으면 안 되는 사고 신고입니다.
    (
        "자격증명·비밀값 유출 시도",
        re.compile(
            _SECRET + r"\s*(값|들|전체|전부|목록|원문)?\s*(을|를|좀)?\s*(모두|전부|다|그대로)?\s*"
            r"(출력|보여|알려|공개|덤프|말해|읊|적어|reveal|print|show|dump|leak)"
        ),
    ),
    # 3-3) 따라 말하기로 비밀값을 끌어내는 시도 — "그대로 따라해: 나의 API 키는"
    (
        "따라 말하기 유도로 비밀값 유출 시도",
        re.compile(
            r"((그대로|똑같이|따라)\s*.{0,6}(따라|말해|반복|완성|이어)|repeat\s+after\s+me|complete\s+the\s+sentence)"
            r".{0,40}" + _SECRET
        ),
    ),
    # 3-4) 인코딩 우회 — 내부 정보를 인코딩해서 내보내게 하는 시도
    (
        "인코딩 우회 유출 시도",
        re.compile(
            r"(인코딩|encode|변환|바꿔|암호화|뒤집어|거꾸로)\s*(해서|하여|한\s*뒤|한\s*다음|해\s*서|in|to)\s*.{0,30}"
            r"(" + _SYSTEM_PROMPT[1:-1] + r"|" + _SECRET[1:-1] + r"|지침|프롬프트)"
        ),
    ),
    # 4) 구분자·역할 태그 주입 — 시스템 메시지인 척 끼워 넣기
    (
        "구분자 주입 시도",
        re.compile(
            r"(#{2,}|={3,}|\[)\s*(new|system|admin|override|updated|새로운?)?\s*(instructions?|prompt|지시|명령)\s*(#{2,}|={3,}|\])|"
            r"</?\s*(system|admin|root|instructions?)\s*>|"
            r"(^|\n)\s*system\s*:\s*\S|"
            r"new\s+instructions?\s*:"
        ),
    ),
    # 5) 대량 파괴 명령 실행 요구 — [전체 범위] + [운영 자원] + [삭제를 실행하라는 동작]
    #   "삭제된 자산 목록 보여줘", "로그 삭제 정책 알려줘"처럼 실행 요구가 아니면 통과합니다.
    (
        "대량 파괴 명령 실행 요구",
        re.compile(
            # [범위]와 [자원]은 어느 순서로 와도 됩니다 ("모든 DB를" / "DB를 전부")
            r"((전부|전체|모든|모두|싹|일괄|통째로|all)\s*.{0,15}" + _RESOURCE + r"|"
            + _RESOURCE + r".{0,10}(전부|전체|모두|싹|일괄|통째로|다\s))"
            r".{0,15}(삭제|지워|지우|날려|드롭|drop|truncate|포맷|wipe|delete)"
            r"\s*(하는\s*명령|명령|해|하라|해라|해줘|해\s*줘|시켜|실행|하자|합시다)|"
            r"rm\s+-rf\s+/|drop\s+(database|table)\s+\w+|truncate\s+table"
        ),
    ),
]

# 가드가 판정 비용을 무한정 쓰지 않도록 검사 길이를 제한합니다.
#   너무 길면 앞뒤를 모두 봅니다(공격 문구를 긴 정상 문장 뒤에 숨기는 경우 대비).
_MAX_SCAN = 4000


def _normalize(text: str) -> str:
    """검사용 정규화. 원문은 바꾸지 않고 사본만 다듬습니다.

    - 소문자화(영문 우회 대비)
    - 폭 0 문자 제거("무​시" 같은 끼워 넣기 우회 대비)
    - 연속 공백을 하나로
    """
    t = text.lower()
    t = re.sub(r"[​-‏⁠﻿]", "", t)
    t = re.sub(r"[ \t\r\f\v]+", " ", t)
    return t


def input_guard(text: str) -> tuple[bool, str]:
    """입력을 검사해 차단 여부를 정합니다.

    Returns:
        (차단할지 여부, 사유 문자열)

    주의: 규칙을 늘릴수록 정상 요청도 막힙니다.
    normal_set에는 "이전", "무시", "새로운 역할", "관리자" 같은 함정 단어가
    일부러 들어 있습니다. 단어 하나로 막으면 오탐이 터집니다.
    """
    # 문자열이 아닌 값이 와도 예외 없이 판정합니다.
    if text is None:
        return False, "통과: 빈 입력 (검사할 내용 없음)"
    if not isinstance(text, str):
        text = str(text)
    if not text.strip():
        return False, "통과: 빈 입력 (검사할 내용 없음)"

    t = _normalize(text)
    if len(t) > _MAX_SCAN:
        half = _MAX_SCAN // 2
        t = t[:half] + "\n" + t[-half:]

    for reason, pattern in _RULES:
        m = pattern.search(t)
        if m:
            snippet = m.group(0).strip()[:40]
            return True, f"차단: {reason} — 감지 구간 '{snippet}'"
    return False, "통과: 지시 덮어쓰기·내부 정보 유출 의도 조합이 감지되지 않음"


# ------------------------------------------------------------------
# PII 마스킹
#
# - 치환 결과([JWT], [AWS_KEY] …)는 어떤 패턴에도 다시 걸리지 않으므로 두 번 돌려도 같습니다(멱등).
# - 가릴 게 없으면 문자열을 전혀 건드리지 않습니다.
# - 순서가 중요합니다: 긴 토큰(JWT)·키를 먼저 가려야 그 안의 일부가 다른 패턴에 잘못 걸리지 않습니다.
# ------------------------------------------------------------------
_PII_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # JWT: header.payload.signature — 헤더가 base64url로 '{"' 로 시작하므로 eyJ 로 시작합니다.
    ("[JWT]", re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]*)?")),
    # AWS 액세스 키 ID: AKIA(장기)/ASIA(임시) + 대문자·숫자 16자
    ("[AWS_KEY]", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    # 이메일
    ("[EMAIL]", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    # 전화번호: 휴대전화(010-1234-5678, 01012345678), 국제표기(+82-10-…), 지역번호(02-123-4567)
    (
        "[PHONE]",
        re.compile(
            r"(?<!\d)(?:\+82[-.\s]?1[016789]|01[016789])[-.\s]?\d{3,4}[-.\s]?\d{4}(?!\d)|"
            r"(?<!\d)0(?:2|[3-6][1-5])[-.\s]\d{3,4}[-.\s]\d{4}(?!\d)"
        ),
    ),
    # 사번: E + 숫자 6자리 (앞뒤로 영숫자가 붙어 있으면 다른 식별자로 보고 건드리지 않습니다)
    ("[EMPLOYEE_ID]", re.compile(r"(?<![A-Za-z0-9])E\d{6}(?![0-9])")),
]


def mask_pii(text: str) -> str:
    """개인정보와 자격증명을 마스킹합니다.

    최소 다섯 가지를 가려야 합니다.
      사번(예: E123456) · 전화번호 · 이메일 · AWS 액세스 키(AKIA...) · JWT(eyJ...)
    """
    if not isinstance(text, str):
        return "" if text is None else mask_pii(str(text))
    out = text
    for placeholder, pattern in _PII_PATTERNS:
        out = pattern.sub(placeholder, out)
    return out


