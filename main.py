import asyncio
from typing import TypedDict, List, Dict, Optional

from langgraph.constants import END
from langgraph.graph import StateGraph
from pathlib import Path

from pdf精读.nodes import load_pdf_node, section_split_node, summarize_sections_node, extract_glossary_node, \
    extract_insights_node, generate_questions_node, save_report_as_pdf
from show_workflow import show_workflow


class SectionSummary(TypedDict):
    title: str
    summary: str
    content: str

class SectionContent(TypedDict):
    title: str
    content: str


class State(TypedDict):
    pdf_path: str
    output_path: str
    paper_title: str
    paper_text: str
    metadata: dict
    sections: List[SectionContent]  # [{"title": ..., "content": ...}]
    summaries: List[SectionSummary]
    glossary: List[dict]  # 专有名词解释
    insights: List[str]
    questions: List[str]



workflow = StateGraph(State)

workflow.add_node("load_pdf", load_pdf_node)
workflow.add_node("split", section_split_node)
workflow.add_node("summarize", summarize_sections_node)
workflow.add_node("glossary_node", extract_glossary_node)
workflow.add_node("insight_node", extract_insights_node)
workflow.add_node("questions_node", generate_questions_node)
workflow.add_node("export", save_report_as_pdf)
# workflow.add_node("export", export_result_node)

# Define edges
workflow.set_entry_point("load_pdf")
workflow.add_edge("load_pdf", "split")
workflow.add_edge("split", "summarize")

workflow.add_edge("summarize", "glossary_node")
workflow.add_edge("summarize", "insight_node")
workflow.add_edge("summarize", "questions_node")
workflow.add_edge("glossary_node", "export")
workflow.add_edge("insight_node", "export")
workflow.add_edge("questions_node", "export")
workflow.add_edge("export", END)

# Compile and run
graph = workflow.compile()
# show_workflow(graph)

if __name__ == "__main__":
    pdf_path = "mmefir.pdf"
    inputs = {"pdf_path": pdf_path,"paper_title": Path(pdf_path).stem}

    async def run_graph():
        result = await graph.ainvoke(inputs)
        print(result)

    asyncio.run(run_graph())

    # from pprint import pprint
    # pprint(final_state["questions"])