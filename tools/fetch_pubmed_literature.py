"""
Fetch PubMed citation metadata and abstracts for TraceDoc demo evidence.

Data source:
  NCBI E-utilities / PubMed

This script stores citation metadata and abstracts, not full-text articles.
It is intended to make the literature evidence layer look like real literature
evidence while avoiding copyrighted full-text scraping.
"""

from __future__ import annotations

import json
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, Iterable, List

import requests


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
KB_DIR = ROOT / "核心三库"
OUT_JSONL = DATA_DIR / "pubmed_literature.jsonl"
OUT_KB = KB_DIR / "PubMed文献证据库.txt"
CACHE_PMIDS = DATA_DIR / "pubmed_pmids_cache.json"

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
TOOL = "TraceDocDemo"
EMAIL = "tracedoc-demo@example.com"

TOPICS = [
    ("呼吸道感染", '("respiratory tract infections"[MeSH Terms] OR cough OR fever) AND primary care', "咳嗽、发热、咳痰、呼吸道感染、上呼吸道感染"),
    ("社区获得性肺炎", '("community-acquired pneumonia" OR "community acquired pneumonia") AND diagnosis', "咳嗽、发热、黄痰、肺炎、胸部影像"),
    ("急性咳嗽", '("acute cough" OR cough) AND (diagnosis OR primary care)', "急性咳嗽、咳痰、咽痛、鼻塞、流涕"),
    ("胸痛", '("chest pain"[MeSH Terms] OR chest pain) AND (triage OR diagnosis)', "胸痛、胸前区疼、胸口疼、出汗、冷汗、放射痛、急诊"),
    ("心悸", '(palpitations OR arrhythmia) AND primary care', "心悸、心律失常、胸闷、胸痛、出汗"),
    ("呼吸困难", '(dyspnea OR breathlessness) AND risk stratification', "呼吸困难、气短、胸闷、喘憋、血氧下降"),
    ("急性腹痛", '("abdominal pain"[MeSH Terms] OR acute abdominal pain) AND diagnosis', "腹痛、肚子疼、胃痛、急腹症、恶心呕吐"),
    ("恶心呕吐", '(nausea OR vomiting) AND emergency OR primary care', "恶心、呕吐、腹痛、脱水、电解质"),
    ("腹泻", '(diarrhea) AND dehydration AND primary care', "腹泻、腹痛、脱水、补液、粪便检查"),
    ("尿路感染", '("urinary tract infections"[MeSH Terms] OR dysuria OR urinary frequency) AND diagnosis', "尿频、尿急、尿痛、尿路感染、尿培养"),
    ("血尿腰痛", '(hematuria AND flank pain) AND diagnosis', "腰痛、背痛、血尿、肾绞痛、泌尿系结石"),
    ("头痛", '("headache"[MeSH Terms] OR acute headache) AND red flags', "头痛、头晕、剧烈头痛、红旗征、头颅CT"),
    ("卒中识别", '(stroke AND FAST AND prehospital) OR (speech disturbance AND weakness AND stroke)', "说话不清楚、言语不清、肢体无力、偏瘫、卒中"),
    ("皮疹瘙痒", '(rash OR pruritus) AND differential diagnosis', "皮疹、瘙痒、红肿、荨麻疹、过敏"),
    ("接触性皮炎", '("dermatitis, contact"[MeSH Terms] OR contact dermatitis) AND cosmetics', "面部红肿、瘙痒、化妆品、接触性皮炎、斑贴试验"),
    ("过敏反应", '(anaphylaxis OR urticaria) AND emergency treatment', "过敏、荨麻疹、喘憋、喉头紧缩、过敏性休克"),
    ("咽痛", '(sore throat OR pharyngitis) AND primary care', "咽痛、喉咙痛、嗓子疼、扁桃体、发热"),
    ("鼻炎", '(rhinitis OR nasal congestion) AND diagnosis', "鼻塞、流涕、流鼻涕、打喷嚏、过敏性鼻炎"),
    ("糖尿病早筛", '(polyuria OR polydipsia) AND diabetes diagnosis', "多饮、多尿、血糖高、体重下降、糖尿病"),
    ("黄疸", '(jaundice) AND diagnosis AND adult', "黄疸、皮肤黄、眼黄、胆红素、肝功能"),
    ("关节痛", '(arthralgia OR joint pain) AND differential diagnosis', "关节痛、关节肿、红肿热痛、炎症指标"),
    ("痛风", '(gout) AND diagnosis AND primary care', "痛风、尿酸、关节红肿热痛、关节痛"),
    ("腰痛", '("low back pain"[MeSH Terms] OR low back pain) AND red flags', "腰痛、背痛、神经缺损、夜间痛、红旗征"),
    ("失眠焦虑", '(insomnia AND anxiety) AND primary care', "失眠、焦虑、情绪低落、睡眠量表、自伤风险"),
    ("异常子宫出血", '("abnormal uterine bleeding" OR vaginal bleeding) AND diagnosis', "阴道出血、月经紊乱、下腹坠痛、妊娠试验、盆腔超声"),
]
TOPIC_KEYWORDS = {topic: keywords for topic, _query, keywords in TOPICS}


def get_json(url: str, params: Dict[str, Any]) -> Dict[str, Any]:
    params = dict(params)
    params.update({"tool": TOOL, "email": EMAIL})
    last_error: Exception | None = None
    for attempt in range(1, 5):
        try:
            resp = requests.get(url, params=params, timeout=(10, 45))
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            last_error = exc
            time.sleep(0.8 * attempt)
    raise RuntimeError(f"GET JSON failed after retries: {last_error}")


def get_text(url: str, params: Dict[str, Any]) -> str:
    params = dict(params)
    params.update({"tool": TOOL, "email": EMAIL})
    last_error: Exception | None = None
    for attempt in range(1, 5):
        try:
            resp = requests.get(url, params=params, timeout=(10, 60))
            resp.raise_for_status()
            return resp.text
        except Exception as exc:
            last_error = exc
            time.sleep(0.8 * attempt)
    raise RuntimeError(f"GET XML failed after retries: {last_error}")


def search_pmids(query: str, retmax: int) -> List[str]:
    data = get_json(
        f"{EUTILS}/esearch.fcgi",
        {
            "db": "pubmed",
            "term": query,
            "retmode": "json",
            "retmax": retmax,
            "sort": "relevance",
        },
    )
    return list(dict.fromkeys(data.get("esearchresult", {}).get("idlist", [])))


def chunks(items: List[str], size: int) -> Iterable[List[str]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def text_of(parent: ET.Element | None, path: str) -> str:
    if parent is None:
        return ""
    node = parent.find(path)
    if node is None:
        return ""
    return " ".join("".join(node.itertext()).split())


def parse_article(article: ET.Element, topic: str) -> Dict[str, Any] | None:
    medline = article.find("MedlineCitation")
    if medline is None:
        return None
    pmid = text_of(medline, "PMID")
    article_node = medline.find("Article")
    if article_node is None or not pmid:
        return None

    title = text_of(article_node, "ArticleTitle")
    journal = text_of(article_node, "Journal/Title")
    year = (
        text_of(article_node, "Journal/JournalIssue/PubDate/Year")
        or text_of(article_node, "Journal/JournalIssue/PubDate/MedlineDate")[:4]
    )
    doi = ""
    for aid in article.findall("PubmedData/ArticleIdList/ArticleId"):
        if aid.attrib.get("IdType") == "doi":
            doi = "".join(aid.itertext()).strip()
            break

    authors = []
    for author in article_node.findall("AuthorList/Author")[:6]:
        last = text_of(author, "LastName")
        initials = text_of(author, "Initials")
        collective = text_of(author, "CollectiveName")
        name = collective or " ".join(x for x in [last, initials] if x)
        if name:
            authors.append(name)

    abstract_parts = []
    for abs_node in article_node.findall("Abstract/AbstractText"):
        label = abs_node.attrib.get("Label")
        text = " ".join("".join(abs_node.itertext()).split())
        if text:
            abstract_parts.append(f"{label}: {text}" if label else text)
    abstract = " ".join(abstract_parts)
    if not title:
        return None

    publication_types = [
        " ".join("".join(pt.itertext()).split()) for pt in article_node.findall("PublicationTypeList/PublicationType")
    ]

    return {
        "topic": topic,
        "pmid": pmid,
        "title": title,
        "authors": authors,
        "journal": journal,
        "year": year,
        "doi": doi,
        "publication_types": publication_types,
        "abstract": abstract,
        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        "source": "PubMed",
    }


def fetch_details(pmids: List[str], topic_by_pmid: Dict[str, str]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for batch in chunks(pmids, 80):
        xml_text = get_text(
            f"{EUTILS}/efetch.fcgi",
            {"db": "pubmed", "id": ",".join(batch), "retmode": "xml"},
        )
        root = ET.fromstring(xml_text)
        for article in root.findall("PubmedArticle"):
            pmid = text_of(article.find("MedlineCitation"), "PMID")
            parsed = parse_article(article, topic_by_pmid.get(pmid, "综合医学文献"))
            if parsed:
                rows.append(parsed)
        time.sleep(0.35)
    return rows


def save_outputs(rows: List[Dict[str, Any]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    KB_DIR.mkdir(parents=True, exist_ok=True)
    with OUT_JSONL.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    blocks = [
        "# PubMed文献证据库",
        "说明：本文件由 NCBI PubMed E-utilities 抓取题录和摘要生成，仅保存公开题录/摘要信息，不包含付费全文。",
    ]
    for i, row in enumerate(rows, start=1):
        authors = ", ".join(row.get("authors") or ["No author listed"])
        pub_types = "; ".join(row.get("publication_types") or [])
        abstract = row.get("abstract") or "PubMed 记录未提供摘要。"
        doi = row.get("doi") or "未提供"
        blocks.append(
            f"""# PMID:{row['pmid']} | {row['title']}
主题：{row.get('topic', '')}
中文关键词：{TOPIC_KEYWORDS.get(row.get('topic', ''), row.get('topic', ''))}
题名：{row['title']}
作者：{authors}
年份：{row.get('year', '')}
期刊：{row.get('journal', '')}
文献类型：{pub_types}
DOI：{doi}
PubMed链接：{row.get('url', '')}
摘要：{abstract[:1600]}"""
        )
    OUT_KB.write_text("\n\n".join(blocks).strip() + "\n", encoding="utf-8")


def main() -> None:
    retmax_per_topic = 20
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    all_pmids: List[str]
    topic_by_pmid: Dict[str, str]
    completed: List[str]
    if CACHE_PMIDS.is_file():
        cache = json.loads(CACHE_PMIDS.read_text(encoding="utf-8"))
        all_pmids = list(cache.get("all_pmids", []))
        topic_by_pmid = dict(cache.get("topic_by_pmid", {}))
        completed = list(cache.get("completed", []))
    else:
        all_pmids = []
        topic_by_pmid = {}
        completed = []

    for topic, query, _keywords in TOPICS:
        if topic in completed:
            continue
        try:
            pmids = search_pmids(query, retmax=retmax_per_topic)
            print(f"[SEARCH] {topic}: {len(pmids)}")
            for pmid in pmids:
                if pmid not in topic_by_pmid:
                    topic_by_pmid[pmid] = topic
                    all_pmids.append(pmid)
            completed.append(topic)
            CACHE_PMIDS.write_text(
                json.dumps(
                    {"all_pmids": all_pmids, "topic_by_pmid": topic_by_pmid, "completed": completed},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception as exc:
            print(f"[WARN] {topic} search failed: {exc}")
        time.sleep(0.5)

    rows = fetch_details(all_pmids, topic_by_pmid)
    rows.sort(key=lambda x: (x.get("topic", ""), x.get("year", ""), x.get("pmid", "")), reverse=True)
    save_outputs(rows)
    print(f"[OK] PubMed records: {len(rows)}")
    print(f"[OK] JSONL: {OUT_JSONL}")
    print(f"[OK] KB: {OUT_KB}")


if __name__ == "__main__":
    main()
