"""Component Builder (T15): 통일된 표준 패턴 → antd를 감싼 공통 컴포넌트 + Storybook 스토리.

- 어떤 컴포넌트가 필요한지와 props 인터페이스는 코드가 결정합니다 (화면 생성이 이 인터페이스를 믿고 호출).
- 구현과 스토리는 LLM이 씁니다 (CLAUDE.md: LLM은 src/components·src/pages만 작성).
- 통일 결정 '변형 유지'는 명시적 prop 으로 반영합니다 (합계 행 → showTotal, 확인 단계 → confirmStep).
- 2회 고쳐도 빌드되지 않는 컴포넌트는 결정적 기본 구현(FALLBACKS)으로 대체하고 그 사실을 기록합니다.
- 결과로 ui_patterns.json (컴포넌트 ↔ ASIS 패턴·사용 화면 매핑)을 남겨 RAG 근거로 씁니다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from src.analyst.unification import load_decisions
from src.config import path as cfg_path
from src.guardrails import check_write_path, find_forbidden_code
from src.llm import default_llm, invoke_structured

FIELD_SPEC = """export interface FieldSpec {
  name: string          // 제출 값의 키
  label: string         // 화면 라벨
  type: 'text' | 'password' | 'select'
  options?: string[]    // select 옵션
  required?: boolean
  testId?: string       // 입력 요소의 data-testid
}"""

SPECS: list[dict[str, Any]] = [
    {"name": "PageLayout", "pattern": "화면 틀(제목·좌측 메뉴)",
     "props": """export interface MenuItem { path: string; label: string }
export interface PageLayoutProps {
  title: string
  testId?: string          // 최상위 요소의 data-testid (화면 표시 확인용)
  menu?: MenuItem[]        // 좌측 메뉴. 항목 클릭 시 react-router 의 useNavigate 로 이동
  children?: React.ReactNode
}""", "rules": "antd Layout(Sider+Content)과 Menu, Typography.Title 로 구성. 최상위 요소에 data-testid={testId}. 메뉴 클릭은 useNavigate 사용."},
    {"name": "SearchPanel", "pattern": "조회조건 영역(기간·유형 선택 + 검색 버튼). 통일 표준: 목록 위에 배치",
     "props": FIELD_SPEC + """
export interface SearchPanelProps {
  fields: FieldSpec[]
  searchLabel?: string                         // 검색 버튼 라벨 (기본 '조회')
  onSearch: (values: Record<string, string>) => void
  searchTestId?: string                        // 검색 버튼 data-testid
}""", "rules": "antd Form(layout='inline') + Input/Input.Password/Select + Button. 목록 위에 두는 가로 배치. 각 입력 요소에 data-testid={field.testId}."},
    {"name": "DataTable", "pattern": "조회 결과 목록 테이블(행·열 데이터). 변형 유지: 합계 행 유무",
     "props": """export interface Column { key: string; title: string }
export interface DataTableProps {
  columns: Column[]
  rows: Record<string, string>[]
  emptyText?: string                 // 행이 없을 때 문구 (기본 '조회된 데이터가 없습니다')
  showTotal?: boolean                // 변형 유지 옵션: 마지막에 합계 행 표시
  totalKey?: string                  // 합계를 낼 금액 컬럼 key ('$1,234.56' 형식 문자열 합산)
  linkColumn?: string                // 이 컬럼 값을 링크로 표시
  onLinkClick?: (row: Record<string, string>) => void
  linkTestId?: string                // 첫 번째 행 링크의 data-testid
  loading?: boolean
}""", "rules": "antd Table 사용. rowKey 는 행 인덱스. 링크는 antd Typography.Link 또는 Button type='link'. 합계 행은 Table summary 사용."},
    {"name": "DetailList", "pattern": "'항목: 값' 상세 정보 표",
     "props": """export interface DetailItem { label: string; value: string }
export interface DetailListProps { items: DetailItem[]; title?: string }""",
     "rules": "antd Descriptions 사용 (bordered, column=2). items 가 비면 아무것도 렌더링하지 않음."},
    {"name": "FormSection", "pattern": "값 입력 폼(텍스트·선택 입력) + 제출 버튼. 변형 유지: 제출 전 확인 단계",
     "props": FIELD_SPEC + """
export interface FormSectionProps {
  fields: FieldSpec[]
  submitLabel: string
  onSubmit: (values: Record<string, string>) => void
  submitTestId?: string              // 제출 버튼 data-testid
  confirmStep?: boolean              // 변형 유지 옵션: true 면 제출 전 확인 모달(Modal.confirm 대신 Modal 컴포넌트 + 확인 버튼)
  loading?: boolean
  error?: string                     // 오류 메시지 (antd Alert)
}""", "rules": "antd Form(layout='vertical') + Input/Input.Password/Select + Button htmlType='submit'. required 필드는 rules 로 검증. 각 입력 요소에 data-testid={field.testId}, 제출 버튼에 data-testid={submitTestId}. confirmStep 이 false 면 바로 onSubmit."},
    {"name": "ResultPanel", "pattern": "제출 처리 결과 화면",
     "props": """export interface ResultPanelProps {
  status: 'success' | 'error'
  title: string
  message?: string
  items?: { label: string; value: string }[]   // 제출한 값 요약
  testId?: string
}""", "rules": "antd Result(status) + Descriptions(items). 최상위 요소에 data-testid={testId}."},
]

FALLBACKS: dict[str, str] = {
    "PageLayout": """import type { ReactNode } from 'react'
import { Layout, Menu, Typography } from 'antd'
import { useNavigate } from 'react-router'
export interface MenuItem { path: string; label: string }
export interface PageLayoutProps { title: string; testId?: string; menu?: MenuItem[]; children?: ReactNode }
export function PageLayout({ title, testId, menu = [], children }: PageLayoutProps) {
  const navigate = useNavigate()
  return (
    <Layout style={{ minHeight: '100vh' }} data-testid={testId}>
      {menu.length > 0 && (
        <Layout.Sider theme="light" width={200}>
          <Menu items={menu.map((m) => ({ key: m.path, label: m.label }))} onClick={(e) => navigate(e.key)} />
        </Layout.Sider>
      )}
      <Layout.Content style={{ padding: 24 }}>
        <Typography.Title level={3}>{title}</Typography.Title>
        {children}
      </Layout.Content>
    </Layout>
  )
}
""",
    "SearchPanel": """import { Button, Form, Input, Select } from 'antd'
export interface FieldSpec { name: string; label: string; type: 'text' | 'password' | 'select'; options?: string[]; required?: boolean; testId?: string }
export interface SearchPanelProps { fields: FieldSpec[]; searchLabel?: string; onSearch: (values: Record<string, string>) => void; searchTestId?: string }
export function SearchPanel({ fields, searchLabel = '조회', onSearch, searchTestId }: SearchPanelProps) {
  return (
    <Form layout="inline" onFinish={(v) => onSearch(v as Record<string, string>)} style={{ marginBottom: 16 }}>
      {fields.map((f) => (
        <Form.Item key={f.name} name={f.name} label={f.label}>
          {f.type === 'select'
            ? <Select data-testid={f.testId} style={{ minWidth: 140 }} options={(f.options ?? []).map((o) => ({ value: o, label: o }))} />
            : <Input data-testid={f.testId} />}
        </Form.Item>
      ))}
      <Button type="primary" htmlType="submit" data-testid={searchTestId}>{searchLabel}</Button>
    </Form>
  )
}
""",
    "DataTable": """import { Button, Table } from 'antd'
export interface Column { key: string; title: string }
export interface DataTableProps { columns: Column[]; rows: Record<string, string>[]; emptyText?: string; showTotal?: boolean; totalKey?: string; linkColumn?: string; onLinkClick?: (row: Record<string, string>) => void; linkTestId?: string; loading?: boolean }
const toNum = (v: string) => Number(String(v ?? '').replace(/[^0-9.-]/g, '')) || 0
export function DataTable({ columns, rows, emptyText = '조회된 데이터가 없습니다', showTotal, totalKey, linkColumn, onLinkClick, linkTestId, loading }: DataTableProps) {
  const cols = columns.map((c) => ({
    key: c.key, dataIndex: c.key, title: c.title,
    render: (v: string, row: Record<string, string>, i: number) => c.key === linkColumn
      ? <Button type="link" data-testid={i === 0 ? linkTestId : undefined} onClick={() => onLinkClick?.(row)}>{v}</Button>
      : v,
  }))
  return (
    <Table rowKey={(_, i) => String(i)} columns={cols} dataSource={rows} loading={loading} pagination={false}
      locale={{ emptyText }}
      summary={showTotal && totalKey ? () => (
        <Table.Summary.Row>
          <Table.Summary.Cell index={0}>합계</Table.Summary.Cell>
          <Table.Summary.Cell index={1}>{rows.reduce((s, r) => s + toNum(r[totalKey]), 0).toFixed(2)}</Table.Summary.Cell>
        </Table.Summary.Row>) : undefined} />
  )
}
""",
    "DetailList": """import { Descriptions } from 'antd'
export interface DetailItem { label: string; value: string }
export interface DetailListProps { items: DetailItem[]; title?: string }
export function DetailList({ items, title }: DetailListProps) {
  if (!items.length) return null
  return <Descriptions bordered column={2} title={title} items={items.map((d, i) => ({ key: String(i), label: d.label, children: d.value }))} />
}
""",
    "FormSection": """import { useState } from 'react'
import { Alert, Button, Form, Input, Modal, Select } from 'antd'
export interface FieldSpec { name: string; label: string; type: 'text' | 'password' | 'select'; options?: string[]; required?: boolean; testId?: string }
export interface FormSectionProps { fields: FieldSpec[]; submitLabel: string; onSubmit: (values: Record<string, string>) => void; submitTestId?: string; confirmStep?: boolean; loading?: boolean; error?: string }
export function FormSection({ fields, submitLabel, onSubmit, submitTestId, confirmStep, loading, error }: FormSectionProps) {
  const [pending, setPending] = useState<Record<string, string> | null>(null)
  const finish = (v: Record<string, string>) => (confirmStep ? setPending(v) : onSubmit(v))
  return (
    <>
      {error && <Alert type="error" message={error} style={{ marginBottom: 16 }} />}
      <Form layout="vertical" onFinish={finish} style={{ maxWidth: 480 }}>
        {fields.map((f) => (
          <Form.Item key={f.name} name={f.name} label={f.label} rules={f.required ? [{ required: true, message: `${f.label}을(를) 입력하세요` }] : []}>
            {f.type === 'select'
              ? <Select data-testid={f.testId} options={(f.options ?? []).map((o) => ({ value: o, label: o }))} />
              : f.type === 'password' ? <Input.Password data-testid={f.testId} /> : <Input data-testid={f.testId} />}
          </Form.Item>
        ))}
        <Button type="primary" htmlType="submit" loading={loading} data-testid={submitTestId}>{submitLabel}</Button>
      </Form>
      <Modal open={!!pending} title="제출 전 확인" onOk={() => { if (pending) onSubmit(pending); setPending(null) }} onCancel={() => setPending(null)}>
        입력한 내용으로 제출할까요?
      </Modal>
    </>
  )
}
""",
    "ResultPanel": """import { Descriptions, Result } from 'antd'
export interface ResultPanelProps { status: 'success' | 'error'; title: string; message?: string; items?: { label: string; value: string }[]; testId?: string }
export function ResultPanel({ status, title, message, items = [], testId }: ResultPanelProps) {
  return (
    <div data-testid={testId}>
      <Result status={status} title={title} subTitle={message} />
      {items.length > 0 && <Descriptions bordered column={1} items={items.map((d, i) => ({ key: String(i), label: d.label, children: d.value }))} />}
    </div>
  )
}
""",
}


class GeneratedComponent(BaseModel):
    component: str = Field(description="컴포넌트 .tsx 파일 전체 코드")
    stories: str = Field(description="Storybook .stories.tsx 파일 전체 코드 (스토리 2개 이상)")


_PROMPT = """당신은 React + TypeScript + Ant Design 6 공통 컴포넌트를 만드는 프론트엔드 개발자입니다.
레거시 화면의 반복 UI 패턴 '{pattern}' 을 차세대 공통 컴포넌트 `{name}` 으로 구현하세요.

[props 인터페이스 — 이름·필드를 그대로 export 하세요. 바꾸지 마세요]
{props}

[구현 규칙]
- {rules}
- 파일은 `export function {name}(props)` 이름 있는 export 하나. default export 금지.
- import 는 react, antd, react-router(필요할 때만) 만 사용. 다른 패키지·외부 URL·dangerouslySetInnerHTML·eval 금지.
- React 타입은 `import type {{ ReactNode }} from 'react'` 처럼 type import 로.
- 표시 문구는 한국어.
{feedback}
[스토리 규칙]
- `import type {{ Meta, StoryObj }} from '@storybook/react-vite'` 와 `import {{ {name} }} from './{name}'` 사용
- `title: 'Common/{name}'`, default export 로 meta, 스토리는 `export const 이름: Story` 로 2개 이상 (기본 상태 + 변형/빈 상태)
- 콜백 props 에는 `() => {{}}` 를 넘기세요. useNavigate 를 쓰는 컴포넌트라면 decorators 로 MemoryRouter(react-router)를 감싸세요.
"""


def _component_specs(domain: str) -> list[dict[str, Any]]:
    """도메인의 통일 결정을 스펙에 반영한 사본 (검색 버튼 표준 라벨 등)."""
    specs = [dict(s) for s in SPECS]
    decisions = load_decisions(domain)
    for d in decisions:
        if d["element_type"] == "action_button" and d["decision"] == "unify" and d.get("standard"):
            for s in specs:
                if s["name"] == "SearchPanel":
                    s["rules"] += f" 검색 버튼 기본 라벨은 통일 표준 '{d['standard']}'."
    return specs


def generate_component(spec: dict[str, Any], feedback: str = "", llm=None) -> GeneratedComponent:
    llm = llm or default_llm(max_tokens=8192)
    fb = f"\n[이전 코드의 빌드 오류 — 반드시 고치세요]\n{feedback}\n" if feedback else ""
    return invoke_structured(llm, GeneratedComponent, _PROMPT.format(
        name=spec["name"], pattern=spec["pattern"], props=spec["props"], rules=spec["rules"], feedback=fb))


def write_component(project: Path, name: str, component: str, stories: str) -> list[str]:
    """컴포넌트·스토리 파일을 씁니다 (G5 쓰기 경로 검사, G4 금지 패턴 검사). 위반 목록을 돌려줍니다."""
    problems = []
    for rel, code in ((f"src/components/{name}.tsx", component), (f"src/components/{name}.stories.tsx", stories)):
        ok, why = check_write_path(rel, project)
        if not ok:
            problems.append(why)
            continue
        bad = find_forbidden_code(code)
        if bad:
            problems.append(f"{rel}: 금지 패턴 {bad}")
        (project / rel).write_text(code, encoding="utf-8")
    return problems


def fallback_stories(name: str) -> str:
    props = {"PageLayout": "{ title: '화면', menu: [{ path: '/a', label: '메뉴' }] }",
             "SearchPanel": "{ fields: [{ name: 'q', label: '검색어', type: 'text' }], onSearch: () => {} }",
             "DataTable": "{ columns: [{ key: 'a', title: '계좌' }], rows: [{ a: '10001' }] }",
             "DetailList": "{ items: [{ label: '계좌', value: '10001' }] }",
             "FormSection": "{ fields: [{ name: 'amount', label: '금액', type: 'text' }], submitLabel: '제출', onSubmit: () => {} }",
             "ResultPanel": "{ status: 'success', title: '완료', items: [{ label: '금액', value: '1' }] }"}[name]
    router = name == "PageLayout"
    return "\n".join([
        "import type { Meta, StoryObj } from '@storybook/react-vite'",
        *(["import { MemoryRouter } from 'react-router'"] if router else []),
        f"import {{ {name} }} from './{name}'", "",
        f"const meta: Meta<typeof {name}> = {{ title: 'Common/{name}', component: {name}"
        + (", decorators: [(S) => <MemoryRouter><S /></MemoryRouter>]" if router else "") + " }",
        "export default meta",
        f"type Story = StoryObj<typeof {name}>", "",
        f"export const Default: Story = {{ args: {props} as never }}",
        f"export const Variant: Story = {{ args: {props} as never }}", ""])


def write_fallback(project: Path, name: str) -> None:
    write_component(project, name, FALLBACKS[name], fallback_stories(name))


def ui_patterns(domain: str, contract: dict[str, Any]) -> dict[str, Any]:
    """컴포넌트 ↔ ASIS 패턴 ↔ 사용 화면 매핑 (결정적). RAG 근거·README에 씁니다."""
    uses: dict[str, list[str]] = {s["name"]: [] for s in SPECS}
    for ep in contract["endpoints"]:
        uses["PageLayout"].append(ep["title"])
        if ep["kind_api"] == "list":
            uses["DataTable"].append(ep["title"])
            if ep.get("filters"):
                uses["SearchPanel"].append(ep["title"])
            if ep.get("details"):
                uses["DetailList"].append(ep["title"])
        elif ep["kind_api"] in ("submit", "login"):
            uses["FormSection"].append(ep["title"])
        elif ep.get("result_of"):
            uses["ResultPanel"].append(ep["title"])
    keep = [d for d in load_decisions(domain) if d["decision"] == "keep_variant"]
    from src.config import fixture_domains_for

    # 이 시스템을 복제한 합성 픽스처의 변형 유지 결정도 함께 (픽스처 이름은 설정·데이터에서 찾음)
    fixture_keep = [d for fx in fixture_domains_for(domain) for d in load_decisions(fx) if d["decision"] == "keep_variant"]
    result = {"domain": domain, "components": [
        {"name": s["name"], "asis_pattern": s["pattern"], "used_by": uses[s["name"]],
         "variant_props": {"DataTable": ["showTotal"], "FormSection": ["confirmStep"]}.get(s["name"], [])}
        for s in SPECS],
        "keep_variant_decisions": [d["role"] for d in keep + fixture_keep]}
    out = cfg_path("analysis") / domain / "ui_patterns.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
