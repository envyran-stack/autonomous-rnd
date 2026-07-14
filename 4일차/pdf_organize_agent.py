"""PDF 문서함 정리 Agent — Step 1 요약 → Step 2 유사 주제별 폴더 정리."""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path

import pymupdf
from dotenv import load_dotenv
from openai import OpenAI

BASE = Path(__file__).resolve().parent
load_dotenv(BASE.parent / ".env")

DOC_LIBRARY = BASE / "samples" / "pdf_samples"
CATALOG_DIR = DOC_LIBRARY / "_catalog"
INDEX_PATH = CATALOG_DIR / "index.json"
ORGANIZATION_PATH = CATALOG_DIR / "organization.json"

MODEL = "gpt-4o-mini"
MAX_TEXT_CHARS = 12_000

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY") or os.getenv("OPEN_API_KEY")
)


def read_pdf_text(pdf_path: Path, max_chars: int = MAX_TEXT_CHARS) -> str:
    doc = pymupdf.open(pdf_path)
    text = "\n".join(page.get_text() for page in doc)
    return text[:max_chars]


def safe_summary_filename(pdf_name: str) -> str:
    stem = Path(pdf_name).stem
    safe = re.sub(r"[^\w가-힣\-]+", "_", stem)[:50].strip("_")
    return f"{safe}.summary.txt"


def safe_folder_name(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*]', "", name).strip()
    cleaned = re.sub(r"\s+", "_", cleaned)
    return cleaned[:60] or "기타"


def list_root_pdfs() -> list[Path]:
    return sorted(
        p for p in DOC_LIBRARY.glob("*.pdf") if p.is_file()
    )


def load_index() -> dict:
    if INDEX_PATH.exists():
        return json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    return {"documents": []}


def save_index(data: dict) -> None:
    CATALOG_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def find_catalog_entry(index: dict, pdf_name: str) -> dict | None:
    for doc in index["documents"]:
        if doc["pdf_name"] == pdf_name:
            return doc
    return None


# ── Step 1: PDF 요약 ─────────────────────────────────────────────


def summarize_pdf(pdf_path: Path, force: bool = False) -> dict:
    """PDF 1개를 요약하고 _catalog에 저장합니다."""
    pdf_name = pdf_path.name
    summary_file = safe_summary_filename(pdf_name)
    summary_path = CATALOG_DIR / summary_file

    index = load_index()
    existing = find_catalog_entry(index, pdf_name)
    if existing and summary_path.exists() and not force:
        print(f"  [skip] 이미 요약됨: {pdf_name}")
        return existing

    print(f"  [요약 중] {pdf_name}")
    text = read_pdf_text(pdf_path)

    prompt = f"""다음 PDF 텍스트를 읽고 아래 형식으로 한국어 요약을 작성하세요.

# 문서 제목

## 유형
(논문 / 보도자료 / 규정 / 매뉴얼 / 기타 중 하나)

## 한 줄 요약

## 핵심 키워드
(쉼표로 구분)

## 이 문서로 답할 수 있는 질문 예시
- 질문1
- 질문2

============= PDF 텍스트 =============
{text}
"""

    response = client.chat.completions.create(
        model=MODEL,
        temperature=0.1,
        messages=[
            {
                "role": "system",
                "content": "당신은 문서 요약 전문가입니다. 형식을 정확히 지키세요.",
            },
            {"role": "user", "content": prompt},
        ],
    )
    summary_text = response.choices[0].message.content or ""

    category = "기타"
    keywords: list[str] = []
    for i, line in enumerate(summary_text.splitlines()):
        if line.strip() == "## 유형" and i + 1 < len(summary_text.splitlines()):
            category = summary_text.splitlines()[i + 1].strip()
        if "핵심 키워드" in line and i + 1 < len(summary_text.splitlines()):
            kw_line = summary_text.splitlines()[i + 1].strip()
            keywords = [k.strip() for k in kw_line.split(",") if k.strip()]

    CATALOG_DIR.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(summary_text, encoding="utf-8")

    entry = {
        "pdf_name": pdf_name,
        "summary_file": summary_file,
        "category": category,
        "keywords": keywords,
    }

    if existing:
        existing.update(entry)
    else:
        index["documents"].append(entry)

    save_index(index)
    print(f"  [완료] {pdf_name} → {summary_file}")
    return entry


def step1_summarize_all(force: bool = False) -> list[dict]:
    """Step 1: pdf_samples 루트의 모든 PDF 요약."""
    print("\n=== Step 1: PDF 요약 ===")
    pdfs = list_root_pdfs()
    if not pdfs:
        print("요약할 PDF가 없습니다.")
        return []

    results = []
    for pdf_path in pdfs:
        results.append(summarize_pdf(pdf_path, force=force))

    print(f"\nStep 1 완료: {len(results)}개 문서 요약")
    return results


# ── Step 2: 유사 PDF 폴더 정리 ───────────────────────────────────


def build_summary_bundle() -> list[dict]:
    index = load_index()
    bundle = []
    for doc in index["documents"]:
        summary_path = CATALOG_DIR / doc["summary_file"]
        summary_text = (
            summary_path.read_text(encoding="utf-8")
            if summary_path.exists()
            else ""
        )
        one_line = ""
        lines = summary_text.splitlines()
        for i, line in enumerate(lines):
            if "한 줄 요약" in line and i + 1 < len(lines):
                one_line = lines[i + 1].strip()
                break

        bundle.append(
            {
                "pdf_name": doc["pdf_name"],
                "category": doc.get("category", ""),
                "keywords": doc.get("keywords", []),
                "one_line_summary": one_line,
                "summary_excerpt": summary_text[:500],
            }
        )
    return bundle


def ask_llm_for_groups(documents: list[dict]) -> dict:
    """LLM에게 유사 문서끼리 묶는 폴더 계획을 요청합니다."""
    response = client.chat.completions.create(
        model=MODEL,
        temperature=0.1,
        messages=[
            {
                "role": "system",
                "content": (
                    "당신은 문서 분류 전문가입니다. "
                    "주제·유형·키워드가 유사한 PDF끼리 같은 폴더로 묶으세요. "
                    "반드시 JSON만 출력하세요."
                ),
            },
            {
                "role": "user",
                "content": f"""아래 PDF 목록을 읽고, 유사한 문서끼리 폴더로 묶는 계획을 세우세요.

규칙:
- 폴더명은 한국어로 짧고 명확하게 (예: 논문_LLM_에이전트, 논문_비전_딥러닝, 규정_학칙, 보도자료_기업)
- 모든 pdf_name은 정확히 한 번만 포함
- 단독 문서도 folder 하나에 넣기

출력 JSON 형식:
{{
  "groups": [
    {{
      "folder_name": "폴더명",
      "reason": "묶은 이유 (한 줄)",
      "pdf_names": ["파일1.pdf", "파일2.pdf"]
    }}
  ]
}}

문서 목록:
{json.dumps(documents, ensure_ascii=False, indent=2)}
""",
            },
        ],
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content or "{}"
    return json.loads(content)


def apply_organization(plan: dict, dry_run: bool = False) -> dict:
    """폴더를 만들고 PDF를 이동합니다."""
    moved = []
    errors = []

    for group in plan.get("groups", []):
        folder_name = safe_folder_name(group.get("folder_name", "기타"))
        target_dir = DOC_LIBRARY / folder_name
        reason = group.get("reason", "")

        if not dry_run:
            target_dir.mkdir(parents=True, exist_ok=True)

        for pdf_name in group.get("pdf_names", []):
            src = DOC_LIBRARY / pdf_name
            dst = target_dir / pdf_name

            if not src.exists():
                errors.append(f"파일 없음: {pdf_name}")
                continue
            if dst.exists() and src.resolve() == dst.resolve():
                continue

            print(f"  {'[dry-run]' if dry_run else '[이동]'} {pdf_name} → {folder_name}/")
            if not dry_run:
                shutil.move(str(src), str(dst))

            moved.append(
                {
                    "pdf_name": pdf_name,
                    "folder": folder_name,
                    "reason": reason,
                }
            )

    index = load_index()
    for doc in index["documents"]:
        for item in moved:
            if doc["pdf_name"] == item["pdf_name"]:
                doc["folder"] = item["folder"]
    if not dry_run:
        save_index(index)
        ORGANIZATION_PATH.write_text(
            json.dumps(plan, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return {"moved": moved, "errors": errors}


def step2_organize(dry_run: bool = False) -> dict:
    """Step 2: 요약본을 읽고 유사 PDF를 폴더별로 정리."""
    print("\n=== Step 2: 유사 PDF 폴더 정리 ===")
    documents = build_summary_bundle()
    if not documents:
        print("요약된 문서가 없습니다. Step 1을 먼저 실행하세요.")
        return {"moved": [], "errors": ["no documents"]}

    print(f"  {len(documents)}개 문서 분류 계획 수립 중...")
    plan = ask_llm_for_groups(documents)

    print("\n  분류 계획:")
    for group in plan.get("groups", []):
        names = ", ".join(group.get("pdf_names", []))
        print(f"    📁 {group.get('folder_name')}: {names}")
        print(f"       이유: {group.get('reason', '')}")

    result = apply_organization(plan, dry_run=dry_run)
    print(f"\nStep 2 완료: {len(result['moved'])}개 이동")
    if result["errors"]:
        print("  오류:", result["errors"])
    return result


# ── Agent 실행 ───────────────────────────────────────────────────


def run_organize_agent(
    force_summarize: bool = False,
    dry_run: bool = False,
) -> None:
    """Step 1 → Step 2 순서로 PDF 정리 Agent를 실행합니다."""
    print("=" * 60)
    print("PDF 정리 Agent 시작")
    print(f"문서함: {DOC_LIBRARY}")
    print("=" * 60)

    step1_summarize_all(force=force_summarize)
    step2_organize(dry_run=dry_run)

    print("\n" + "=" * 60)
    print("PDF 정리 Agent 완료")
    if dry_run:
        print("(dry-run 모드: 실제 파일 이동은 하지 않았습니다)")
    print("=" * 60)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="PDF 유사 주제별 정리 Agent")
    parser.add_argument(
        "--step",
        choices=["1", "2", "all"],
        default="all",
        help="실행할 단계 (1=요약, 2=정리, all=전체)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="이미 요약된 PDF도 다시 요약",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Step 2에서 이동 계획만 출력 (파일 이동 안 함)",
    )
    args = parser.parse_args()

    if args.step == "1":
        step1_summarize_all(force=args.force)
    elif args.step == "2":
        step2_organize(dry_run=args.dry_run)
    else:
        run_organize_agent(force_summarize=args.force, dry_run=args.dry_run)
