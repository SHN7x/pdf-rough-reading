import asyncio
import json

import pdfkit
import fitz  # PyMuPDF
import markdown2
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter


from pdf精读.utils.json_util import repair_json_output

llm = ChatOpenAI(model="deepseek-v3")
# llm2 = ChatOpenAI(model="gpt-4o-mini")
llm2 = ChatOpenAI(model="claude-sonnet-4-20250514")
# llm2 = ChatOpenAI(model="deepseek-reasoner-all")

def load_pdf_node(state: dict) -> dict:
    pdf_path = state["pdf_path"]
    doc = fitz.open(pdf_path)
    text = "\n".join([page.get_text() for page in doc])
    metadata = doc.metadata
    return {
        # **state,
        "paper_text": text,
        "metadata": metadata
    }


with open("prompts/split.txt", "r", encoding="utf-8") as f:
    SPLIT_PROMPT = f.read()

# 控制并发批量（防止 API 超限）
semaphore = asyncio.Semaphore(5)

async def process_chunk_limited(chunk, prompt_template, llm):
    async with semaphore:
        return await process_chunk(chunk, prompt_template, llm)

async def process_chunk(chunk: str, prompt_template: str, llm) -> list[dict]:
    prompt = PromptTemplate.from_template(prompt_template)
    try:
        response = await llm.ainvoke(prompt.format(text=chunk))
        content = repair_json_output(response.content)
        sections = json.loads(content)
        return sections
    except Exception as e:
        print(f"[⚠️ 警告] 分块处理失败: {e}")
        print("\n====================有问题的chunk内容：\n",chunk)
        return []

def section_split_node(state: dict) -> dict:
    import nest_asyncio
    nest_asyncio.apply()  # 适用于 Jupyter 等 REPL 环境

    text = state["paper_text"]

    # 使用claude输入全文
    prompt = PromptTemplate.from_template(SPLIT_PROMPT)
    response = llm2.invoke(prompt.format(text=text))
    content = repair_json_output(response.content)
    all_sections_lists = json.loads(content)

    # # 1. 自动分块（避免截断重要章节）
    # splitter = RecursiveCharacterTextSplitter(chunk_size=7000, chunk_overlap=2000)
    # chunks = splitter.split_text(text)

    # # 顺序执行llm，太慢了
    # all_sections = []
    # for i, chunk in enumerate(chunks):
    #     print(f"⏳ 正在处理第{i+1}/{len(chunks)}块")
    #     prompt = PromptTemplate.from_template(SPLIT_PROMPT)
    #     response = llm2.invoke(prompt.format(text=chunk))
    #     try:
    #         content = repair_json_output(response.content)
    #         sections = json.loads(content)
    #     except json.JSONDecodeError:
    #         print(f"[警告] 第{i+1}块解析失败，原始内容：", response.content)
    #         continue
    #     all_sections.extend(sections)





# 2. 合并重复标题（可选）



    # print(f"📄 共需处理 {len(chunks)} 个块，正在并行调用 LLM...")
    #
    # # # 并行调度所有 chunk    #
    # tasks = [
    #     process_chunk_limited(chunk, SPLIT_PROMPT, llm)
    #     for chunk in chunks
    # ]
    # all_sections_lists = asyncio.run(asyncio.gather(*tasks))
    #
    # # 平铺所有块的输出（去掉空的）
    all_sections = [sec for section_list in all_sections_lists for sec in section_list]
    #

    merged = {}
    for sec in all_sections:
        title = sec["title"].strip().capitalize()
        if title in merged:
            merged[title] += "\n" + sec["content"].strip()
        else:
            merged[title] = sec["content"].strip()

    final_sections = [{"title": k, "content": v} for k, v in merged.items()]
    print(f"✅ 完成章节分割，共 {len(final_sections)} 段")

    # debug 保存
    with open("temp/final_sections.json", "w", encoding="utf-8") as f:
        json.dump(final_sections, f, ensure_ascii=False, indent=2)

    # debug 读取
    # with open("temp/final_sections.json", "r", encoding="utf-8") as f:
    #     final_sections = json.load(f)


    return {
        # **state,
        "sections": final_sections
    }


with open("prompts/summary.txt", "r", encoding="utf-8") as f:
    SUMMARY_PROMPT = f.read()

async def summarize_sections_node(state: dict) -> dict:
    sections = state["sections"]
    summaries = []

    # semaphore = asyncio.Semaphore(5)
    #
    # async def summarize_section(section):
    #     async with semaphore:
    #         prompt = PromptTemplate.from_template(SUMMARY_PROMPT)
    #         try:
    #             response = await llm.ainvoke(prompt.format(
    #                 title=section["title"],
    #                 content=section["content"]
    #             ))
    #             return {
    #                 "title": section["title"],
    #                 "summary": response.content.strip(),
    #                 "content": section["content"]
    #             }
    #         except Exception as e:
    #             print(f"[⚠️ 摘要失败] {section['title']} - {e}")
    #             return {
    #                 "title": section["title"],
    #                 "summary": "[摘要失败]",
    #                 "content": section["content"],
    #             }
    #
    # tasks = [summarize_section(sec) for sec in sections]
    # summaries = await asyncio.gather(*tasks)
    #
    # print("摘要节点结束")
    #
    # # debug 保存
    # with open("temp/summaries.json", "w", encoding="utf-8") as f:
    #     json.dump(summaries, f, ensure_ascii=False, indent=2)

    # # debug 读取
    with open("temp/summaries.json", "r", encoding="utf-8") as f:
        summaries = json.load(f)

    return {
        # **state,
        "summaries": summaries
    }



with open("prompts/glossary.txt", "r", encoding="utf-8") as f:
    GLOSSARY_PROMPT = f.read()

async def extract_glossary_node(state: dict) -> dict:
    summaries = state["summaries"]
    # semaphore = asyncio.Semaphore(5)
    #
    # async def extract_glossary(section):
    #     async with semaphore:
    #         try:
    #             prompt_template = PromptTemplate.from_template(GLOSSARY_PROMPT)
    #             response = await llm.ainvoke(prompt_template.format(
    #                 title=section["title"],
    #                 content=section["content"],
    #                 summary = section["summary"],
    #             ))
    #             return json.loads(repair_json_output(response.content))
    #         except Exception as e:
    #             print(f"[⚠️术语提取失败] {section['title']} - {e}")
    #             return []
    #
    # tasks = [extract_glossary(sec) for sec in summaries]
    # glossary_list = await asyncio.gather(*tasks)
    # raw_glossary = [item for sublist in glossary_list for item in sublist]  # 扁平化
    #
    # # 专业术语去重
    # seen = set()
    # glossary = []
    # for item in raw_glossary:
    #     term = item.get("term", "").strip()
    #     if not term:
    #         continue
    #     normalized_term = term.capitalize()
    #     if normalized_term not in seen:
    #         seen.add(normalized_term)
    #         glossary.append(item)
    #
    #
    # # debug 保存
    # with open("temp/glossary.json", "w", encoding="utf-8") as f:
    #     json.dump(glossary, f, ensure_ascii=False, indent=2)

    # # debug 读取
    with open("temp/glossary.json", "r", encoding="utf-8") as f:
        glossary = json.load(f)

    return {
        # **state,
        "glossary": glossary
    }


with open("prompts/insights.txt", "r", encoding="utf-8") as f:
    INSIGHTS_PROMPT = f.read()

async def extract_insights_node(state: dict) -> dict:
    summaries = state["summaries"]
    # semaphore = asyncio.Semaphore(5)
    #
    # async def extract_insights(section):
    #     async with semaphore:
    #         try:
    #             prompt_template = PromptTemplate.from_template(INSIGHTS_PROMPT)
    #             response = await llm.ainvoke(prompt_template.format(
    #                 title=section["title"],
    #                 summary=section["summary"],
    #                 content=section["content"],
    #             ))
    #             return [response.content]
    #         except Exception as e:
    #             print(f"[⚠️提取 insight 失败] {section['title']} - {e}")
    #             return []
    #
    # tasks = [extract_insights(sec) for sec in summaries]
    # insight_list = await asyncio.gather(*tasks)
    # insights = [ins for sublist in insight_list for ins in sublist]
    #
    # with open("temp/insights.json", "w", encoding="utf-8") as f:
    #     json.dump(insights, f, ensure_ascii=False, indent=2)

    # # debug 读取
    with open("temp/insights.json", "r", encoding="utf-8") as f:
        insights = json.load(f)

    return {
        # **state,
        "insights": insights
    }


with open("prompts/questions.txt", "r", encoding="utf-8") as f:
    QUESTIONS_PROMPT = f.read()

async def generate_questions_node(state: dict) -> dict:
    summaries = state["summaries"]

    # semaphore = asyncio.Semaphore(5)
    #
    # async def gen_questions(section):
    #     async with semaphore:
    #         try:
    #             prompt_template = PromptTemplate.from_template(QUESTIONS_PROMPT)
    #             response = await llm.ainvoke(prompt_template.format(
    #                 title=section["title"],
    #                 summary=section["summary"],
    #                 content=section["content"],
    #             ))
    #             return [response.content]
    #         except Exception as e:
    #             print(f"[⚠️提问生成失败] {section['title']} - {e}")
    #             return []
    #
    # tasks = [gen_questions(sec) for sec in summaries]
    # questions_list = await asyncio.gather(*tasks)
    # questions = [q for sublist in questions_list for q in sublist]
    #
    # with open("temp/questions.json", "w", encoding="utf-8") as f:
    #     json.dump(questions, f, ensure_ascii=False, indent=2)

    # # debug 读取
    with open("temp/questions.json", "r", encoding="utf-8") as f:
        questions = json.load(f)

    return {
        # **state,
        "questions": questions
    }


def generate_final_report(state: dict) -> str:
    summaries = state.get("summaries", [])
    glossary = state.get("glossary", [])
    insights = state.get("insights", [])
    questions = state.get("questions", [])
    paper_title = state["paper_title"]
    report = [f"# 📘 精读报告：{paper_title}", ""]

    # 一、摘要
    report.append("## 📝 一、章节摘要\n")
    for sec in summaries:
        report.append(f"### {sec['title']}\n{sec['summary']}\n")

    # 二、术语表
    report.append("## 🧠 二、术语表（Glossary）\n")
    report.append("| 术语 | 解释 |\n|------|------|")
    for item in glossary:
        report.append(f"| {item['term']} | {item['definition']} |")

    # 三、核心洞察
    report.append("\n## 💡 三、核心洞察（Insights）\n")
    for insight in insights:
        report.append(f"- {insight}")

    # 四、阅读问题
    report.append("\n## ❓ 四、推荐阅读问题（Questions）\n")
    for q in questions:
        report.append(f"- {q}")

    return "\n".join(report)

def save_report_as_pdf(state: dict):
    markdown_text = generate_final_report(state)
    output_path = "report.pdf"
    html_content = markdown2.markdown(markdown_text)

    # 添加简单样式美化 PDF
    html_template = f"""
    <html>
    <head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: 'Arial', sans-serif; line-height: 1.6; margin: 2em; }}
        h1 {{ color: #2c3e50; }}
        h2 {{ color: #34495e; margin-top: 1.5em; }}
        table {{ border-collapse: collapse; width: 100%; }}
        table, th, td {{ border: 1px solid #ccc; padding: 8px; }}
        th {{ background-color: #f4f4f4; }}
    </style>
    </head>
    <body>
    {html_content}
    </body>
    </html>
    """

    options = {
        "encoding": "UTF-8",
        "page-size": "A4",
        "margin-top": "0.75in",
        "margin-right": "0.75in",
        "margin-bottom": "0.75in",
        "margin-left": "0.75in",
    }

    pdfkit.from_string(html_template, output_path, options=options)
    print(f"✅ PDF saved to {output_path}")
    return {
        "output_path": output_path
    }