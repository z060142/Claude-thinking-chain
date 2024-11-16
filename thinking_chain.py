# thinking_chain.py
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass
from enum import Enum
import json
import re
try:
    import json5
except ImportError:
    logging.warning("未安裝json5，將使用自定義JSON處理")
    json5 = None

class PhaseStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    FAILED = "failed"
    NEED_REVISION = "need_revision"

class PhaseAction(Enum):
    PROCEED = "proceed"
    RECURSE = "recurse"
    REVISE = "revise"
    COMPLETE = "complete"

@dataclass
class PhaseResult:
    """階段結果"""
    content: str
    quality_score: float
    issues: List[str]
    suggestions: List[str]
    next_action: PhaseAction

    def to_dict(self) -> dict:
        """轉換為可序列化的字典"""
        return {
            "content": self.content,
            "quality_score": self.quality_score,
            "issues": self.issues,
            "suggestions": self.suggestions,
            "next_action": self.next_action.value  # 轉換枚舉為字符串
        }

class ThinkingPhase:
    """思考階段"""
    def __init__(self, name: str, requirements: dict):
        self.name = name
        self.requirements = requirements
        self.results: Optional[PhaseResult] = None
        self.status = PhaseStatus.PENDING
        self.attempt_count = 0
        self.max_attempts = 3
        
    def to_dict(self) -> dict:
        """轉換為字典格式"""
        return {
            "name": self.name,
            "requirements": self.requirements,
            "status": self.status.value,  # 轉換枚舉為字符串
            "results": self.results.to_dict() if self.results else None,
            "attempt_count": self.attempt_count
        }

class ThinkingChain:
    """思考鏈主類"""
    def __init__(self, api_handler):
        self.api_handler = api_handler
        self.phases: List[ThinkingPhase] = []
        self.context: Dict = {}
        self.original_query: str = ""
        self.max_improvement_attempts = 2
        
    def _preprocess_json_text(self, text: str) -> str:
        """更嚴格的JSON文本預處理"""
        import re
        
        def escape_string(s: str) -> str:
            """轉義字符串中的特殊字符"""
            escape_chars = {
                '"': '\\"',
                '\\': '\\\\',
                '\n': '\\n',
                '\r': '\\r',
                '\t': '\\t',
                '\b': '\\b',
                '\f': '\\f'
            }
            return ''.join(escape_chars.get(c, c) for c in s)
        
        def process_json_value(match: re.Match) -> str:
            """處理JSON值部分的文本"""
            content = match.group(1)
            if content.strip().startswith('{') or content.strip().startswith('['):
                # 如果是嵌套的JSON對象或數組，遞迴處理
                return f': {self._preprocess_json_text(content)}'
            else:
                # 如果是字符串值，進行轉義
                escaped = escape_string(content)
                return f': "{escaped}"'
        
        # 1. 首先清理基本格式
        text = text.strip()
        
        # 2. 處理鍵值對
        # 匹配JSON鍵值對模式: "key": value 或 "key":value
        pattern = r'"([^"]+)"\s*:\s*(.+?)(?=,|\s*[}\]]|$)'
        
        def replace_pair(match: re.Match) -> str:
            key = match.group(1)
            value = match.group(2)
            
            # 如果值是字符串且包含換行符
            if value.strip().startswith('"') and '\n' in value:
                # 移除開始和結束的引號，處理內容
                value = value.strip().strip('"')
                value = escape_string(value)
                return f'"{key}": "{value}"'
            
            return f'"{key}": {value}'
        
        # 3. 應用處理
        text = re.sub(pattern, replace_pair, text, flags=re.DOTALL)
        
        # 4. 移除任何剩餘的不合法字符
        text = re.sub(r'[\x00-\x1F\x7F]', '', text)
        
        return text
        
    def _clean_json_string(self, json_str: str) -> str:
        """清理JSON字符串，保留換行符但處理其他控制字符"""
        # 將Windows風格換行轉換為Unix風格
        json_str = json_str.replace('\r\n', '\n')
    
        # 處理縮進
        lines = json_str.split('\n')
        cleaned_lines = []
        for line in lines:
            # 保留實際內容的縮進，但移除多餘的空白
            cleaned_line = line.rstrip()
            if cleaned_line:  # 不是空行
                cleaned_lines.append(cleaned_line)
    
        # 重新組合成字符串
        return '\n'.join(cleaned_lines)

    # 新增處理特殊字符的方法
    def _escape_special_chars(self, text: str) -> str:
        """轉義特殊字符，而不是清除它們"""
        escape_map = {
            '"': '\\"',
            '\\': '\\\\',
            '\b': '\\b',
            '\f': '\\f',
            '\n': '\\n',
            '\r': '\\r',
            '\t': '\\t'
        }
        return ''.join(escape_map.get(c, c) for c in text)

    def _build_framework_prompt(self, query: str) -> str:
        """構建框架定義prompt"""
        return f"""Analyze the following query and design a thinking framework.
The framework MUST include analysis phases followed by an execution phase.
The execution phase should focus on producing the actual requested output (code, story, etc.).

Query: {query}

Guidelines:
1. Analyze if this query requires:
   - Code generation
   - Creative writing
   - Analysis report
   - Other specific output

2. Design appropriate analysis phases

3. ALWAYS end with an execution phase that produces the requested output

Required format:
<framework>
{{
    "query_type": "code_generation|creative_writing|analysis|other",
    "final_output_type": "description of what needs to be produced",
    "phases": [
        {{
            "name": "phase_name",
            "type": "analysis|execution",
            "requirements": {{
                "input": "what is needed as input",
                "objective": "what this phase should achieve",
                "success_criteria": "what determines success"
            }}
        }}
    ],
    "success_criteria": {{
        "overall_objective": "main goal to achieve",
        "quality_metrics": ["list of quality metrics"]
    }}
}}
</framework>

Example:
For a code generation query, the last phase should be "Code Generation"
For a story writing query, the last phase should be "Story Creation"
For an analysis query, the last phase should be "Final Report Generation"
"""

    def _build_phase_prompt(self, phase: ThinkingPhase) -> str:
        """構建階段執行prompt"""
        # 獲取之前所有階段的結果
        previous_results = {
            name: content for name, content in self.context.items()
            if name != phase.name
        }
        
        # 判斷是否是執行階段
        is_execution_phase = phase == self.phases[-1]
        
        if is_execution_phase:
            return self._build_execution_phase_prompt(phase, previous_results)
        else:
            return self._build_analysis_phase_prompt(phase, previous_results)

    def _build_analysis_phase_prompt(self, phase: ThinkingPhase, previous_results: Dict) -> str:
        """構建分析階段prompt"""
        return f"""Execute the following analysis phase:

Phase: {phase.name}
Requirements: {json.dumps(phase.requirements, indent=2)}
Previous Results: {json.dumps(previous_results, indent=2)}
Original Query: {self.original_query}

Please format your response as follows:
<phase_output>
{{
    "analysis": "your detailed analysis",
    "conclusions": ["key conclusions"],
    "quality_check": {{
        "score": 0-100,
        "issues": ["any issues found"],
        "suggestions": ["improvement suggestions"]
    }},
    "next_action": "proceed|recurse|revise"
}}
</phase_output>
"""

    def _build_execution_phase_prompt(self, phase: ThinkingPhase, previous_results: Dict) -> str:
        """構建執行階段prompt"""
        return f"""This is the EXECUTION phase. Based on all previous analyses, please produce the final output as requested in the original query.

Original Query: {self.original_query}

Previous Analyses:
{json.dumps(previous_results, indent=2)}

Requirements: {json.dumps(phase.requirements, indent=2)}

IMPORTANT: Your response should focus on producing the actual requested output (code, story, etc.), not just analysis.

Please format your response as follows:
<phase_output>
{{
    "analysis": "brief execution summary",
    "output": "your actual implementation/creation/output",
    "quality_check": {{
        "score": 0-100,
        "issues": ["any issues found"],
        "suggestions": ["improvement suggestions"]
    }},
    "next_action": "proceed|recurse|revise"
}}
</phase_output>
"""

    def _parse_framework_response(self, response: Dict) -> bool:
        """解析框架定義響應"""
        try:
            content = response['content']
            # 提取 <framework> 標記中的內容
            start = content.find('<framework>') + len('<framework>')
            end = content.find('</framework>')
            if start == -1 or end == -1:
                logging.error(f"完整回應內容: {content}")
                raise ValueError("未找到框架定義標記")
                
            framework_str = content[start:end].strip()
            framework_str = self._clean_json_string(framework_str)
            
            # 在解析前輸出用於調試
            logging.debug(f"準備解析的JSON: {framework_str}")
            
            try:
                framework = json.loads(framework_str)
            except json.JSONDecodeError as e:
                logging.error(f"JSON解析錯誤: {str(e)}")
                logging.error(f"問題JSON: {framework_str}")
                raise
            
            # 創建思考階段
            self.phases = [
                ThinkingPhase(phase['name'], phase['requirements'])
                for phase in framework['phases']
            ]
            
            # 保存框架信息
            self.context['framework'] = framework
            return True
            
        except Exception as e:
            logging.error(f"解析框架響應時出錯: {str(e)}")
            return False
            
        except Exception as e:
            logging.error(f"解析框架響應時出錯: {str(e)}")
            return False
            
    def _parse_phase_response(self, response: Dict) -> PhaseResult:
        """解析階段執行響應"""
        try:
            content = response['content']
            start = content.find('<phase_output>') + len('<phase_output>')
            end = content.find('</phase_output>')
            if start == -1 or end == -1:
                raise ValueError("未找到階段輸出標記")
                
            output_str = content[start:end].strip()
            
            try:
                # 預處理JSON文本
                processed_str = self._preprocess_json_text(output_str)
                logging.debug(f"處理後的JSON: {processed_str}")
                
                # 嘗試解析
                try:
                    output = json.loads(processed_str)
                except json.JSONDecodeError as e:
                    logging.error(f"標準JSON解析失敗: {str(e)}")
                    if json5:
                        logging.info("嘗試使用json5解析")
                        output = json5.loads(processed_str)
                    else:
                        raise
                
                # 提取內容，恢復換行符
                content = output.get('output', output.get('analysis', ''))
                content = content.replace('\\n', '\n')
                
                return PhaseResult(
                    content=content,
                    quality_score=output['quality_check']['score'],
                    issues=output['quality_check']['issues'],
                    suggestions=output['quality_check']['suggestions'],
                    next_action=PhaseAction(output['next_action'])
                )
                
            except Exception as e:
                logging.error(f"JSON解析錯誤: {str(e)}")
                logging.error(f"原始JSON: {output_str}")
                logging.error(f"處理後的JSON: {processed_str}")
                raise
                
        except Exception as e:
            logging.error(f"解析階段響應時出錯: {str(e)}")
            raise
            
    def _format_output(self, value: str) -> str:
        """格式化輸出值，確保JSON兼容"""
        if isinstance(value, str):
            # 替換換行符為\n，移除其他控制字符
            value = value.replace('\n', '\\n')
            value = ''.join(char for char in value if ord(char) >= 32 or char == '\n')
        return value

    def _build_phase_prompt(self, phase: ThinkingPhase) -> str:
        """構建階段執行prompt，加入格式說明"""
        # 獲取之前所有階段的結果
        previous_results = {
           name: content for name, content in self.context.items()
            if name != phase.name
        }
    
        # 判斷是否是執行階段
        is_execution_phase = phase == self.phases[-1]
    
        # 基礎prompt
        if is_execution_phase:
            base_prompt = self._build_execution_phase_prompt(phase, previous_results)
        else:
            base_prompt = self._build_analysis_phase_prompt(phase, previous_results)

        # 添加格式指導
        format_guide = """
Note on output format:
1. For multiline text, use \\n to indicate line breaks
2. Avoid using raw newlines in JSON values
3. Properly escape all special characters
4. Keep JSON structure clean and valid
"""
        return base_prompt + format_guide
        
    def init_framework(self, query: str) -> bool:
        """初始化思考框架"""
        self.original_query = query
        prompt = self._build_framework_prompt(query)
        response = self.api_handler.send_prompt(prompt)
        return self._parse_framework_response(response)
        
    def execute_phase(self, phase: ThinkingPhase) -> bool:
        """執行單個思考階段"""
        try:
            phase.status = PhaseStatus.IN_PROGRESS
            phase.attempt_count += 1
            
            prompt = self._build_phase_prompt(phase)
            response = self.api_handler.send_prompt(prompt)
            
            try:
                result = self._parse_phase_response(response)
                phase.results = result
                
                # 更新階段狀態
                if result.quality_score >= 80 and result.next_action == PhaseAction.PROCEED:
                    phase.status = PhaseStatus.COMPLETE
                    return True
                elif result.next_action == PhaseAction.RECURSE and phase.attempt_count < phase.max_attempts:
                    phase.status = PhaseStatus.NEED_REVISION
                    return self.execute_phase(phase)
                else:
                    phase.status = PhaseStatus.FAILED
                    return False
                    
            except json.JSONDecodeError as e:
                logging.error(f"JSON解析失敗: {str(e)}")
                if not json5:
                    logging.info("嘗試安裝json5以改善JSON解析: pip install json5")
                phase.status = PhaseStatus.FAILED
                return False
            
            # 檢查是否是最後一個階段且分數低於100
            is_last_phase = phase == self.phases[-1]
            
            if is_last_phase and result.quality_score < 95 and phase.attempt_count < self.max_improvement_attempts:
                logging.info(f"最後階段分數較低 ({result.quality_score}), 嘗試改進...")
                
                # 構建改進提示
                improvement_prompt = self._build_improvement_prompt(phase, result)
                
                # 記錄原始結果
                original_result = result
                
                # 嘗試改進
                try:
                    improvement_response = self.api_handler.send_prompt(improvement_prompt)
                    improved_result = self._parse_phase_response(improvement_response)
                    
                    # 如果改進後的分數更高，使用改進後的結果
                    if improved_result.quality_score > original_result.quality_score:
                        logging.info(f"改進成功! 新分數: {improved_result.quality_score}")
                        phase.results = improved_result
                    else:
                        logging.info("改進未能提高分數，保留原始結果")
                        
                except Exception as e:
                    logging.error(f"改進嘗試失敗: {str(e)}")
                    # 保留原始結果
                    
            if result.quality_score >= 80 and result.next_action == PhaseAction.PROCEED:
                phase.status = PhaseStatus.COMPLETE
                return True
            elif result.next_action == PhaseAction.RECURSE and phase.attempt_count < phase.max_attempts:
                phase.status = PhaseStatus.NEED_REVISION
                return self.execute_phase(phase)
            else:
                phase.status = PhaseStatus.FAILED
                return False
                
        except Exception as e:
            logging.error(f"執行階段 {phase.name} 時出錯: {str(e)}")
            phase.status = PhaseStatus.FAILED
            return False

    def _build_improvement_prompt(self, phase: ThinkingPhase, result: PhaseResult) -> str:
        """構建改進提示"""
        suggestions_text = "\n".join(f"- {s}" for s in result.suggestions)
        issues_text = "\n".join(f"- {i}" for i in result.issues) if result.issues else "No specific issues identified."
        
        return f"""Please improve the previous analysis based on the following suggestions and issues:

Previous Analysis:
{result.content}

Quality Score: {result.quality_score}

Issues to Address:
{issues_text}

Suggestions for Improvement:
{suggestions_text}

Original Requirements:
{json.dumps(phase.requirements, indent=2)}

Please provide an improved analysis that addresses these points and aims for a higher quality score.
Use the same output format as before:

<phase_output>
{{
    "analysis": "your improved analysis",
    "conclusions": ["your improved conclusions"],
    "quality_check": {{
        "score": 0-100,
        "issues": ["any remaining issues"],
        "suggestions": ["any additional suggestions"]
    }},
    "next_action": "proceed|recurse|revise"
}}
</phase_output>
"""

    def run(self, query: str) -> List[Dict]:
        """執行完整思考鏈"""
        if not self.init_framework(query):
            raise Exception("初始化思考框架失敗")
            
        results = []
        for phase in self.phases:
            success = self.execute_phase(phase)
            results.append(phase.to_dict())
            
            # 將階段結果添加到上下文
            if phase.results:
                self.context[phase.name] = phase.results.content
                
            if not success:
                logging.error(f"階段 {phase.name} 執行失敗")
                break
                
        return results

# 測試代碼
if __name__ == "__main__":
    from config import load_config
    from api_handler import APIHandler
    
    # 設置更詳細的日誌級別
    logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        config = load_config()
        api_handler = APIHandler(config)
        thinking_chain = ThinkingChain(api_handler)
        
        # 測試簡單查詢
        test_query = "What are the three main benefits of regular exercise?"
        print(f"\n處理查詢: '{test_query}'")
        
        results = thinking_chain.run(test_query)
        
        print("\n思考鏈結果:")
        for result in results:
            print(f"\n階段: {result['name']}")
            print(f"狀態: {result['status']}")
            if result['results']:
                print(f"結論: {result['results']['content'][:200]}...")
                print(f"品質分數: {result['results']['quality_score']}")
        
        # 顯示使用量報告
        usage_report = api_handler.get_usage_report()
        print("\n使用量報告:")
        print(f"總Token數: {usage_report['usage']['total_tokens']}")
        print(f"估計成本: ${usage_report['estimated_cost']:.4f}")
        
    except Exception as e:
        logging.error(f"測試過程中出錯: {str(e)}")
        print(f"\n錯誤: {str(e)}")