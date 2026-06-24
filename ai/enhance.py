import os
import json
import sys
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any
from queue import Queue
from threading import Lock
# INSERT_YOUR_CODE
import requests

import dotenv
import argparse
from tqdm import tqdm

import langchain_core.exceptions
from langchain_openai import ChatOpenAI
from langchain.prompts import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
)
from structure import Structure

if os.path.exists('.env'):
    dotenv.load_dotenv()
template = open("template.txt", "r").read()
system = open("system.txt", "r").read()


class FatalAIProviderError(RuntimeError):
    pass


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=str, required=True, help="jsonline data file")
    parser.add_argument("--max_workers", type=int, default=1, help="Maximum number of parallel workers")
    return parser.parse_args()


def is_chinese_language(language: str) -> bool:
    normalized = (language or "").strip().lower().replace("_", "-")
    return normalized in {"chinese", "zh", "zh-cn", "simplified chinese", "simplified-chinese", "\u4e2d\u6587", "\u7b80\u4f53\u4e2d\u6587"}


def has_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text or ""))


def same_content(left: str, right: str) -> bool:
    normalize = lambda value: re.sub(r"\s+", " ", (value or "").strip()).lower()
    return bool(normalize(left)) and normalize(left) == normalize(right)


def compact_sentence(text: str, max_chars: int = 60) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return ""
    parts = re.split(r"(?<=[\u3002\uff01\uff1f.!?])\s*", text)
    for part in parts:
        part = part.strip()
        if part and len(part) <= max_chars:
            return part
    return text if len(text) <= max_chars else text[: max_chars - 3].rstrip() + "..."


def has_chinese_ai_content(item: Dict, language: str) -> bool:
    """Return True only when the record has real translated Chinese AI content."""
    if not is_chinese_language(language):
        return bool(item.get("AI", {}).get("translated_summary", "").strip())

    ai_data = item.get("AI", {}) if isinstance(item.get("AI", {}), dict) else {}
    translated_summary = ai_data.get("translated_summary", "")
    if not translated_summary.strip() or not has_cjk(translated_summary):
        return False

    core_fields = (
        "tldr",
        "research_problem",
        "key_innovation",
        "motivation",
        "method",
        "result",
        "conclusion",
    )
    return any(has_cjk(ai_data.get(field, "")) for field in core_fields)

def normalize_ai_fields(item: Dict, language: str, default_ai_fields: Dict) -> Dict:
    ai_data = item.get("AI", {}) if isinstance(item.get("AI", {}), dict) else {}
    ai_data = {**default_ai_fields, **ai_data}
    source_summary = item.get("summary", "")
    translated_summary = ai_data.get("translated_summary", "")
    chinese_output = is_chinese_language(language)

    if chinese_output and (
        not translated_summary.strip()
        or not has_cjk(translated_summary)
        or same_content(translated_summary, source_summary)
    ):
        translated_summary = ""
        ai_data["translated_summary"] = ""

    tldr = ai_data.get("tldr", "")
    tldr_is_invalid = (
        not tldr.strip()
        or same_content(tldr, translated_summary)
        or same_content(tldr, source_summary)
        or len(tldr.strip()) > 90
    )

    if chinese_output and tldr.strip() and not has_cjk(tldr):
        tldr_is_invalid = True

    if tldr_is_invalid:
        for key in ("conclusion", "result", "key_innovation", "research_problem"):
            candidate = ai_data.get(key, "")
            if chinese_output and candidate and not has_cjk(candidate):
                continue
            candidate = compact_sentence(candidate, 60 if chinese_output else 120)
            if candidate and not same_content(candidate, translated_summary):
                tldr = candidate
                break
        else:
            tldr = "" if chinese_output else compact_sentence(source_summary, 120)

    if chinese_output and tldr and not has_cjk(tldr):
        tldr = ""

    ai_data["tldr"] = compact_sentence(tldr, 60 if chinese_output else 120)
    return ai_data


def parse_json_object(text: str) -> Dict[str, Any]:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            return json.loads(cleaned[start : end + 1])
        raise


def normalize_anthropic_base_url() -> str:
    base_url = (os.environ.get("ANTHROPIC_BASE_URL") or "").strip().rstrip("/")
    if not base_url:
        return ""

    lowered = base_url.lower()
    if lowered.endswith("/v1/messages") or lowered.endswith("/messages"):
        return base_url
    if lowered.endswith("/v1"):
        return f"{base_url}/messages"
    return f"{base_url}/v1/messages"


class AnthropicJSONChain:
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        self.endpoint = normalize_anthropic_base_url()
        if not self.api_key or not self.endpoint:
            raise RuntimeError("ANTHROPIC_API_KEY and ANTHROPIC_BASE_URL are required for Anthropic-compatible mode")

    def invoke(self, inputs: Dict[str, str]) -> Structure:
        language = inputs["language"]
        content = inputs["content"]
        field_names = [
            "tldr",
            "translated_summary",
            "research_problem",
            "key_innovation",
            "motivation",
            "method",
            "experiments",
            "result",
            "conclusion",
            "limitations",
        ]
        json_instruction = (
            "\n\nReturn only one valid JSON object. Do not wrap it in markdown. "
            f"The JSON keys must be exactly: {', '.join(field_names)}. "
            "Every value must be a string."
        )
        payload = {
            "model": self.model_name,
            "max_tokens": 2048,
            "temperature": 0.2,
            "system": system.format(language=language),
            "messages": [
                {
                    "role": "user",
                    "content": template.format(language=language, content=content) + json_instruction,
                }
            ],
        }
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
            "anthropic-version": "2023-06-01",
        }
        try:
            response = requests.post(self.endpoint, headers=headers, json=payload, timeout=90)
        except requests.RequestException as e:
            raise RuntimeError(f"Anthropic-compatible API request failed: {e}") from e

        if response.status_code in {401, 403, 404}:
            raise FatalAIProviderError(
                f"Anthropic-compatible API configuration error {response.status_code}: {response.text[:500]}"
            )
        if response.status_code >= 400:
            raise RuntimeError(f"Anthropic-compatible API error {response.status_code}: {response.text[:500]}")

        data = response.json()
        text_parts = []
        for block in data.get("content", []):
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block.get("text", ""))
        if not text_parts and isinstance(data.get("completion"), str):
            text_parts.append(data["completion"])

        parsed = parse_json_object("\n".join(text_parts))
        normalized = {field: "" for field in field_names}
        normalized.update({key: str(value) if value is not None else "" for key, value in parsed.items()})
        return Structure(**normalized)

def process_single_item(chain, item: Dict, language: str) -> Dict:
    def is_sensitive(content: str) -> bool:
        """
        调用 spam.dw-dengwei.workers.dev 接口检测内容是否包含敏感词。
        返回 True 表示触发敏感词，False 表示未触发。
        """
        if os.environ.get("ENABLE_SENSITIVE_FILTER", "false").lower() not in {"1", "true", "yes"}:
            return False

        try:
            resp = requests.post(
                "https://spam.dw-dengwei.workers.dev",
                json={"text": content},
                timeout=5
            )
            if resp.status_code == 200:
                result = resp.json()
                # 约定接口返回 {"sensitive": true/false, ...}
                return result.get("sensitive", True)
            else:
                # 如果接口异常，默认不触发敏感词
                print(f"Sensitive check failed with status {resp.status_code}", file=sys.stderr)
                return False
        except Exception as e:
            print(f"Sensitive check error: {e}", file=sys.stderr)
            return False

    def check_github_code(content: str) -> Dict:
        """提取并验证 GitHub 链接"""
        code_info = {}

        # 1. 优先匹配 github.com/owner/repo 格式
        github_pattern = r"https?://github\.com/([a-zA-Z0-9-_]+)/([a-zA-Z0-9-_\.]+)"
        match = re.search(github_pattern, content)
        
        if match:
            owner, repo = match.groups()
            # 清理 repo 名称，去掉可能的 .git 后缀或末尾的标点
            repo = repo.rstrip(".git").rstrip(".,)")
            
            full_url = f"https://github.com/{owner}/{repo}"
            code_info["code_url"] = full_url
            
            # 尝试调用 GitHub API 获取信息
            github_token = os.environ.get("TOKEN_GITHUB")
            headers = {"Accept": "application/vnd.github.v3+json"}
            if github_token:
                headers["Authorization"] = f"token {github_token}"
            
            try:
                api_url = f"https://api.github.com/repos/{owner}/{repo}"
                resp = requests.get(api_url, headers=headers, timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    code_info["code_stars"] = data.get("stargazers_count", 0)
                    code_info["code_last_update"] = data.get("pushed_at", "")[:10]
            except Exception:
                # API 调用失败不影响主流程
                pass
            return code_info

        # 2. 如果没有 github.com，尝试匹配 github.io
        github_io_pattern = r"https?://[a-zA-Z0-9-_]+\.github\.io(?:/[a-zA-Z0-9-_\.]+)*"
        match_io = re.search(github_io_pattern, content)
        
        if match_io:
            url = match_io.group(0)
            # 清理末尾标点
            url = url.rstrip(".,)")
            code_info["code_url"] = url
            # github.io 不进行 star 和 update 判断
                
        return code_info

    # 检查 summary 字段
    if is_sensitive(item.get("summary", "")):
        return None

    # 检测代码可用性
    code_info = check_github_code(item.get("summary", ""))
    if code_info:
        item.update(code_info)

    """处理单个数据项"""
    # Default structure with meaningful fallback values
    default_ai_fields = {
        "tldr": "",
        "translated_summary": "",
        "research_problem": "",
        "key_innovation": "",
        "motivation": "",
        "method": "",
        "experiments": "",
        "result": "",
        "conclusion": "",
        "limitations": ""
    }
    
    try:
        response: Structure = chain.invoke({
            "language": language,
            "content": item['summary']
        })
        item['AI'] = response.model_dump()
    except FatalAIProviderError:
        raise
    except langchain_core.exceptions.OutputParserException as e:
        # 尝试从错误信息中提取 JSON 字符串并修复
        error_msg = str(e)
        partial_data = {}
        
        if "Function Structure arguments:" in error_msg:
            try:
                # 提取 JSON 字符串
                json_str = error_msg.split("Function Structure arguments:", 1)[1].strip().split('are not valid JSON')[0].strip()
                # 预处理 LaTeX 数学符号 - 使用四个反斜杠来确保正确转义
                json_str = json_str.replace('\\', '\\\\')
                # 尝试解析修复后的 JSON
                partial_data = json.loads(json_str)
            except Exception as json_e:
                print(f"Failed to parse JSON for {item.get('id', 'unknown')}: {json_e}", file=sys.stderr)
        
        # Merge partial data with defaults to ensure all fields exist
        item['AI'] = {**default_ai_fields, **partial_data}
        print(f"Using partial AI data for {item.get('id', 'unknown')}: {list(partial_data.keys())}", file=sys.stderr)
    except Exception as e:
        # Catch any other exceptions and provide default values
        print(f"Unexpected error for {item.get('id', 'unknown')}: {e}", file=sys.stderr)
        item['AI'] = default_ai_fields
    
    # Final validation to ensure all required fields exist and do not show English fallbacks as Chinese.
    for field in default_ai_fields.keys():
        if field not in item['AI']:
            item['AI'][field] = default_ai_fields[field]
    item['AI'] = normalize_ai_fields(item, language, default_ai_fields)

    # 检查 AI 生成的所有字段
    for v in item.get("AI", {}).values():
        if is_sensitive(str(v)):
            return None
    return item


def normalize_openai_base_url() -> str:
    base_url = (os.environ.get("OPENAI_BASE_URL") or "").strip()
    if not base_url:
        return ""

    normalized = base_url.rstrip("/")
    suffix = "/chat/completions"
    if normalized.lower().endswith(suffix):
        normalized = normalized[: -len(suffix)].rstrip("/")
        os.environ["OPENAI_BASE_URL"] = normalized
        print(
            "Normalized OPENAI_BASE_URL by removing trailing /chat/completions",
            file=sys.stderr,
        )

    return normalized

def process_all_items(data: List[Dict], model_name: str, language: str, max_workers: int) -> List[Dict]:
    """Process all data items, using Anthropic-compatible mode when configured."""
    use_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY") and os.environ.get("ANTHROPIC_BASE_URL"))
    if use_anthropic:
        chain = AnthropicJSONChain(model_name)
        print('Connect to Anthropic-compatible:', model_name, file=sys.stderr)
    else:
        normalize_openai_base_url()
        llm = ChatOpenAI(model=model_name).with_structured_output(Structure, method="function_calling")
        print('Connect to OpenAI-compatible:', model_name, file=sys.stderr)

        prompt_template = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(system),
            HumanMessagePromptTemplate.from_template(template=template)
        ])

        chain = prompt_template | llm

    processed_data = [None] * len(data)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_idx = {
            executor.submit(process_single_item, chain, item, language): idx
            for idx, item in enumerate(data)
        }

        for future in tqdm(
            as_completed(future_to_idx),
            total=len(data),
            desc="Processing items"
        ):
            idx = future_to_idx[future]
            try:
                result = future.result()
                processed_data[idx] = result
            except FatalAIProviderError as e:
                for pending in future_to_idx:
                    pending.cancel()
                raise RuntimeError(str(e)) from e
            except Exception as e:
                print(f"Item at index {idx} generated an exception: {e}", file=sys.stderr)
                processed_data[idx] = data[idx]
                processed_data[idx]['AI'] = {
                    "tldr": "",
                    "translated_summary": "",
                    "research_problem": "",
                    "key_innovation": "",
                    "motivation": "",
                    "method": "",
                    "experiments": "",
                    "result": "",
                    "conclusion": "",
                    "limitations": ""
                }

    return processed_data

def main():
    args = parse_args()
    model_name = os.environ.get("ANTHROPIC_MODEL") or os.environ.get("MODEL_NAME", 'deepseek-chat')
    language = os.environ.get("LANGUAGE") or 'Chinese'

    # 检查并删除目标文件
    target_file = args.data.replace('.jsonl', f'_AI_enhanced_{language}.jsonl')
    if os.path.exists(target_file):
        os.remove(target_file)
        print(f'Removed existing file: {target_file}', file=sys.stderr)

    # 读取数据
    data = []
    with open(args.data, "r") as f:
        for line in f:
            data.append(json.loads(line))

    # 去重
    seen_ids = set()
    unique_data = []
    for item in data:
        if item['id'] not in seen_ids:
            seen_ids.add(item['id'])
            unique_data.append(item)

    data = unique_data
    print('Open:', args.data, file=sys.stderr)
    
    # 并行处理所有数据
    processed_data = process_all_items(
        data,
        model_name,
        language,
        args.max_workers
    )
    
    # 保存结果
    written_count = 0
    valid_ai_count = 0
    skipped_invalid_ai_count = 0
    chinese_output = is_chinese_language(language)
    with open(target_file, "w", encoding="utf-8") as f:
        for item in processed_data:
            if item is None:
                continue
            has_valid_ai = has_chinese_ai_content(item, language)
            if chinese_output and not has_valid_ai:
                skipped_invalid_ai_count += 1
                continue

            f.write(json.dumps(item, ensure_ascii=False) + "\n")
            written_count += 1
            if has_valid_ai:
                valid_ai_count += 1

    if data and written_count == 0:
        raise RuntimeError(
            f"AI enhancement produced 0 records from {len(data)} input records; refusing to write an empty dataset"
        )

    if data and is_chinese_language(language) and valid_ai_count == 0:
        raise RuntimeError(
            "AI enhancement produced no valid Chinese translations. "
            "Check ANTHROPIC_API_KEY/ANTHROPIC_BASE_URL/ANTHROPIC_MODEL or OPENAI_BASE_URL/OPENAI_API_KEY/MODEL_NAME; refusing to publish empty AI fields."
        )

    print(
        f"Wrote {written_count} AI-enhanced records to {target_file}; "
        f"valid AI records: {valid_ai_count}; skipped invalid AI records: {skipped_invalid_ai_count}",
        file=sys.stderr,
    )

if __name__ == "__main__":
    main()
