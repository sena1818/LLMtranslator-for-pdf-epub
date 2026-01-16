"""
LangGraph 驱动的翻译 Agent - 带术语一致性检查与自我修正
架构: Translator -> QA Checker -> [Pass | Fixer] -> Output
"""

import os
import json
import time
from typing import List, Dict, TypedDict, Annotated
from dotenv import load_dotenv
import logging
from pathlib import Path

# === 核心库 ===
#from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_text_splitters import RecursiveCharacterTextSplitter

# LangGraph 核心组件
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('translation_langgraph.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()

# === 配置 ===
API_KEY = os.getenv("SILICONFLOW_API_KEY")
if not API_KEY:
    raise ValueError("请在 .env 文件中填入 SILICONFLOW_API_KEY!")

INPUT_PATH = "/Users/sena/Desktop/LLMAgent/translator/marker_output/Cyclonopedia/Cyclonopedia.md"
OUTPUT_PATH = "/Users/sena/Desktop/LLMAgent/translator/output_final/Cyclonopedia_CN_V2.md"
GLOSSARY_PATH = "/Users/sena/Desktop/LLMAgent/translator/glossary.json"
PROGRESS_PATH = "/Users/sena/Desktop/LLMAgent/translator/progress_v2.json"


SILICON_BASE_URL = "https://api.siliconflow.cn/v1"

# 初始化 LLM (使用两个不同温度的实例)
llm_translator = ChatOpenAI(
    model="deepseek-ai/DeepSeek-V3", 
    temperature=0.3, 
    api_key=API_KEY,
    base_url=SILICON_BASE_URL
)

llm_checker = ChatOpenAI(
    model="deepseek-ai/DeepSeek-V3", 
    temperature=0.1, 
    api_key=API_KEY,
    base_url=SILICON_BASE_URL
)

# === 定义状态结构 ===
class TranslationState(TypedDict):
    """工作流状态"""
    chunk_index: int
    original_text: str
    translation: str
    context: str
    glossary: Dict[str, str]
    qa_result: Dict  # {"pass": bool, "issues": List[str]}
    retry_count: int
    max_retries: int


# === 工具函数 ===
def split_text(text: str) -> List[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=2000,
        chunk_overlap=200,
        separators=["\n\n", "\n", ".", "!", "?", " ", ""]
    )
    return splitter.split_text(text)


def load_progress() -> Dict:
    if os.path.exists(PROGRESS_PATH):
        with open(PROGRESS_PATH, 'r') as f:
            return json.load(f)
    return {"last_index": -1, "failed_chunks": []}


def save_progress(index: int, failed_chunks: List[int]):
    with open(PROGRESS_PATH, 'w') as f:
        json.dump({"last_index": index, "failed_chunks": failed_chunks}, f)


# === 节点 1: 翻译器 ===
def translator_node(state: TranslationState) -> TranslationState:
    """核心翻译节点"""
    logger.info(f"📝 [Chunk {state['chunk_index']}] 开始翻译...")
    
    prompt_template = """
你是一位精通后现代哲学、克苏鲁神话与地缘政治的专业翻译家。
你正在翻译 Reza Negarestani 的著作《Cyclonopedia》。

【核心术语表】(必须严格遵守):
{glossary}

【上文语境】:
{context}

【待翻译文本】:
{text}

---
【翻译要求】:
1. 保留 Markdown 格式 (标题、加粗、链接)
2. 风格: 学术、晦涩、带理论虚构感
3. 专有名词首次出现时保留英文
4. **严格使用术语表中的译名**
5. 直接输出译文，无需前言

翻译:
"""
    
    prompt = ChatPromptTemplate.from_template(prompt_template)
    chain = prompt | llm_translator | StrOutputParser()
    
    try:
        translation = chain.invoke({
            "glossary": "\n".join([f"- {en}: {zh}" for en, zh in state["glossary"].items()]),
            "context": state["context"][-800:],
            "text": state["original_text"]
        })
        
        state["translation"] = translation
        logger.info(f"✅ [Chunk {state['chunk_index']}] 翻译完成")
        
    except Exception as e:
        logger.error(f"❌ [Chunk {state['chunk_index']}] 翻译失败: {e}")
        state["translation"] = f"[翻译失败: {str(e)}]"
    
    return state


# === 节点 2: 质检器 ===
def qa_checker_node(state: TranslationState) -> TranslationState:
    """术语一致性检查"""
    logger.info(f"🔍 [Chunk {state['chunk_index']}] 开始质检...")
    
    issues = []
    
    # 1. 检查术语表遵守情况
    for en_term, zh_term in state["glossary"].items():
        # 如果原文包含该术语
        if en_term.lower() in state["original_text"].lower():
            # 检查译文是否使用了正确的中文术语
            if zh_term not in state["translation"]:
                issues.append(f"术语 '{en_term}' 应翻译为 '{zh_term}'，但未在译文中找到")
    
    # 2. 检查是否有未翻译的大段英文 (超过20个连续英文单词)
    import re
    long_english = re.findall(r'[a-zA-Z]+(?:\s+[a-zA-Z]+){19,}', state["translation"])
    if long_english:
        issues.append(f"检测到未翻译的长段落: {long_english[0][:50]}...")
    
    # 3. 检查 Markdown 格式是否保留
    original_headers = re.findall(r'^#+\s', state["original_text"], re.MULTILINE)
    translated_headers = re.findall(r'^#+\s', state["translation"], re.MULTILINE)
    if len(original_headers) != len(translated_headers):
        issues.append(f"标题数量不匹配: 原文{len(original_headers)}个, 译文{len(translated_headers)}个")
    
    # 判定结果
    if issues:
        logger.warning(f"⚠️ [Chunk {state['chunk_index']}] 发现 {len(issues)} 个问题")
        state["qa_result"] = {"pass": False, "issues": issues}
    else:
        logger.info(f"✅ [Chunk {state['chunk_index']}] 质检通过")
        state["qa_result"] = {"pass": True, "issues": []}
    
    return state


# === 节点 3: 修复器 ===
def fixer_node(state: TranslationState) -> TranslationState:
    """根据质检结果自动修正"""
    logger.info(f"🔧 [Chunk {state['chunk_index']}] 开始修复...")
    
    state["retry_count"] += 1
    
    # 构建修复提示
    issues_text = "\n".join([f"- {issue}" for issue in state["qa_result"]["issues"]])
    
    prompt_template = """
你是翻译质量修正专家。以下是一段翻译及其存在的问题，请修正这些问题。

【原文】:
{original}

【当前译文】:
{translation}

【发现的问题】:
{issues}

【术语表】(必须严格遵守):
{glossary}

---
【修正要求】:
1. 只修正上述问题，不要改动其他部分
2. 确保使用术语表中的标准译名
3. 保持原有的 Markdown 格式
4. 直接输出修正后的完整译文

修正后的译文:
"""
    
    prompt = ChatPromptTemplate.from_template(prompt_template)
    chain = prompt | llm_checker | StrOutputParser()
    
    try:
        fixed_translation = chain.invoke({
            "original": state["original_text"],
            "translation": state["translation"],
            "issues": issues_text,
            "glossary": "\n".join([f"- {en}: {zh}" for en, zh in state["glossary"].items()])
        })
        
        state["translation"] = fixed_translation
        logger.info(f"✅ [Chunk {state['chunk_index']}] 修复完成")
        
    except Exception as e:
        logger.error(f"❌ [Chunk {state['chunk_index']}] 修复失败: {e}")
    
    return state


# === 路由函数 ===
def should_continue(state: TranslationState) -> str:
    """决定下一步: 通过、修复、或放弃"""
    
    # 如果还没检查过，先去检查
    if "qa_result" not in state or not state["qa_result"]:
        return "qa_checker"
    
    # 检查通过，结束流程
    if state["qa_result"]["pass"]:
        return "end"
    
    # 检查未通过，但还有重试机会
    if state["retry_count"] < state["max_retries"]:
        return "fixer"
    
    # 超过最大重试次数，放弃修复
    logger.warning(f"⚠️ [Chunk {state['chunk_index']}] 超过最大重试次数，放弃修复")
    return "end"


# === 构建 LangGraph 工作流 ===
def create_translation_workflow():
    """创建翻译工作流图"""
    
    workflow = StateGraph(TranslationState)
    
    # 添加节点
    workflow.add_node("translator", translator_node)
    workflow.add_node("qa_checker", qa_checker_node)
    workflow.add_node("fixer", fixer_node)
    
    # 设置入口点
    workflow.set_entry_point("translator")
    
    # 添加边 (流程控制)
    workflow.add_edge("translator", "qa_checker")
    workflow.add_conditional_edges(
        "qa_checker",
        should_continue,
        {
            "fixer": "fixer",
            "end": END
        }
    )
    workflow.add_edge("fixer", "qa_checker")  # 修复后重新检查
    
    # 编译图
    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)
    
    return app


# === 主程序 ===
def main():
    logger.info(f"📖 读取文件: {INPUT_PATH}")
    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        full_text = f.read()

    # 加载术语表
    glossary = {}
    if os.path.exists(GLOSSARY_PATH):
        with open(GLOSSARY_PATH, "r", encoding="utf-8") as f:
            glossary = json.load(f)
            logger.info(f"📚 术语表加载成功: {len(glossary)} 个词条")

    # 切割文本
    chunks = split_text(full_text)
    logger.info(f"✂️ 文本切割完成: 共 {len(chunks)} 个块")

    # 加载进度
    progress = load_progress()
    start_index = progress["last_index"] + 1
    failed_chunks = progress["failed_chunks"]
    
    if start_index > 0:
        logger.info(f"🔄 从第 {start_index + 1} 块继续")
    else:
        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            f.write("> 本书由 LangGraph 驱动的 AI Agent 自动翻译\n")
            f.write("> 包含术语一致性检查与自我修正机制\n\n")

    # 创建工作流
    app = create_translation_workflow()
    
    # 翻译主循环
    context = ""
    
    for i in range(start_index, len(chunks)):
        logger.info(f"\n{'='*60}")
        logger.info(f"🚀 开始处理 Chunk {i+1}/{len(chunks)}")
        logger.info(f"{'='*60}")
        
        # 初始化状态
        initial_state = {
            "chunk_index": i + 1,
            "original_text": chunks[i],
            "translation": "",
            "context": context,
            "glossary": glossary,
            "qa_result": {},
            "retry_count": 0,
            "max_retries": 2  # 最多修复2次
        }
        
        # 运行工作流
        config = {"configurable": {"thread_id": f"chunk_{i}"}}
        
        try:
            final_state = None
            for state in app.stream(initial_state, config):
                final_state = state
            
            # 提取最终状态
            if final_state:
                # LangGraph 返回的是 {node_name: state} 的字典
                last_node = list(final_state.keys())[-1]
                result_state = final_state[last_node]
                
                translation = result_state["translation"]
                
                # 写入文件
                with open(OUTPUT_PATH, "a", encoding="utf-8") as f:
                    f.write(translation + "\n\n")
                
                # 更新上下文
                context = translation[-800:]
                
                # 保存进度
                save_progress(i, failed_chunks)
                
                # 短暂休息
                time.sleep(8)
                
        except Exception as e:
            logger.error(f"❌ Chunk {i+1} 处理失败: {e}")
            failed_chunks.append(i)
            save_progress(i, failed_chunks)
            
            with open(OUTPUT_PATH, "a", encoding="utf-8") as f:
                f.write(f"\n\n[处理失败 - Chunk {i+1}]\n{chunks[i][:200]}...\n\n")

    # 总结
    logger.info(f"\n{'='*60}")
    logger.info(f"✅ 翻译完成! 输出文件: {OUTPUT_PATH}")
    if failed_chunks:
        logger.warning(f"⚠️ 有 {len(failed_chunks)} 个块处理失败: {failed_chunks}")
    logger.info(f"{'='*60}")


if __name__ == "__main__":
    main()