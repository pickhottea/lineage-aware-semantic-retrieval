#!/usr/bin/env python3
from __future__ import annotations

import argparse, json, re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

PARA_RX = re.compile(r"\[(\d{4})\]")

# 排除：明顯的章節 heading（只抓很像標題的情況，避免誤殺）
HEADING_BAD = re.compile(
    r"^\s*(technical field|field|background|description of related art|related art)\b",
    re.I,
)

# summary 不是全部排除：只排除「純目標宣告」那種
SUMMARY_BAD = re.compile(r"^\s*(summary|brief summary)\b\s*$", re.I)

# 保留：比較像在「描述/定義/結構關係」的動詞
KEEP_EXPLAIN = re.compile(
    r"\b(is|are|includes?|comprises?|has|have|formed|provided|arranged|disposed|mounted|coupled|connected|configured|wherein)\b",
    re.I,
)

def load_jsonl(p: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out

def normalize_text(t: str) -> str:
    return (t or "").strip()

def looks_like_heading_bad(text: str) -> bool:
    # 只看第一行，避免正文中提到 "technical field" 被誤殺
    first = text.splitlines()[0].strip().lower()
    return bool(HEADING_BAD.search(first))

def is_focus_type(ct: str) -> bool:
    # 你目前 focus 來源是 spec_def/spec_summary/spec_embodiment
    # 這裡容忍未知，但至少要 spec_ 開頭
    return ct.startswith("spec_")

def is_hard_noise(text: str) -> bool:
    t = normalize_text(text)
    if not t:
        return True
    if looks_like_heading_bad(t):
        return True
    if SUMMARY_BAD.match(t):
        return True
    return False

def is_good_focus(text: str) -> bool:
    t = normalize_text(text)
    if not t:
        return False
    # 必須有解釋性動詞，否則多半是圖說/碎片
    if not KEEP_EXPLAIN.search(t):
        return False
    return True

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", default="artifacts/chunks_spec_all_v1.jsonl")
    ap.add_argument("--out", default="artifacts/chunks_spec_focus_v3.jsonl")
    ap.add_argument("--min_per_family", type=int, default=12, help="ensure at least N focus chunks per family")
    args = ap.parse_args()

    rows = load_jsonl(args.in_path)

    by_family: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        fid = str(r.get("family_id") or "")
        by_family[fid].append(r)

    kept: List[Dict[str, Any]] = []

    # A) 先依規則挑「真的像定義/結構描述」的段落
    kept_by_family: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for fid, rs in by_family.items():
        for r in rs:
            ct = str(r.get("chunk_type") or "")
            if not is_focus_type(ct):
                continue
            txt = normalize_text(r.get("text") or "")
            if is_hard_noise(txt):
                continue
            if not is_good_focus(txt):
                continue
            kept_by_family[fid].append(r)

    # B) 每個 family 保底：如果太少，就補「非 TF/BG 的一般段落」
    #    這一步是為了避免你 mapping 時 where=family_id 直接 0 hits
    for fid, rs in by_family.items():
        cur = kept_by_family.get(fid, [])
        if len(cur) >= args.min_per_family:
            kept.extend(cur)
            continue

        # 候補：同 family、chunk_type 是 spec_、且不是硬噪音
        cand: List[Dict[str, Any]] = []
        for r in rs:
            ct = str(r.get("chunk_type") or "")
            if not is_focus_type(ct):
                continue
            txt = normalize_text(r.get("text") or "")
            if is_hard_noise(txt):
                continue
            cand.append(r)

        # 先放已挑到的，再補到 min_per_family
        out = list(cur)
        need = args.min_per_family - len(out)
        if need > 0:
            out.extend(cand[:need])

        kept.extend(out)

    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    with outp.open("w", encoding="utf-8") as f:
        for r in kept:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    fam_cnt = sum(1 for _ in {str(r.get("family_id") or "") for r in kept})
    print("[done] wrote", outp)
    print("  total_in =", len(rows), "kept_focus =", len(kept), "families =", fam_cnt)

if __name__ == "__main__":
    main()
