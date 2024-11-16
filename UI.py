# ui.py
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from tkinter import font as tkfont
import json
import logging
import sys
import os
from typing import Optional
from datetime import datetime
from config import load_config
from api_handler import APIHandler
from thinking_chain import ThinkingChain
import threading
import queue

# 創建logs目錄
current_dir = os.path.dirname(os.path.abspath(__file__))
logs_dir = os.path.join(current_dir, 'logs')
os.makedirs(logs_dir, exist_ok=True)

# 設置日誌
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(logs_dir, 'ui_debug.log'))
    ]
)

class ChatUI:
    def __init__(self, root):
        logging.info("Initializing ChatUI")
        self.root = root
        self.root.title("Claude Thinking Chain")
        
        # 初始化API和思考鏈
        try:
            self.config = load_config()
            self.api_handler = APIHandler(self.config)
            self.thinking_chain = ThinkingChain(self.api_handler)
            logging.info("API handler and thinking chain initialized")
        except Exception as e:
            logging.error(f"Failed to initialize API: {str(e)}")
            messagebox.showerror("Error", f"Failed to initialize API: {str(e)}")
            raise
        
        # 創建消息隊列
        self.message_queue = queue.Queue()
        
        # 設定視窗大小
        self.root.geometry("1200x800")
        
        # UI初始化
        self._setup_styles()
        self.main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.main_paned.pack(fill=tk.BOTH, expand=True)
        
        self.chat_frame = ttk.Frame(self.main_paned)
        self.thinking_frame = ttk.Frame(self.main_paned)
        self.main_paned.add(self.chat_frame, weight=1)
        self.main_paned.add(self.thinking_frame, weight=1)
        
        self._init_chat_area()
        self._init_thinking_area()
        
        # 開始消息處理循環
        self.root.after(100, self._process_message_queue)
        
        logging.info("ChatUI initialization completed")

    def _setup_styles(self):
        """設定文字樣式"""
        logging.debug("Setting up styles")
        # 使用更通用的字體
        self.chat_font = tkfont.Font(family="Noto_Sans_CJK_TC_Regular", size=10)
        self.code_font = tkfont.Font(family="Noto_Serif_CJK_TC_Regular", size=10)
    
        # 設定標籤樣式
        style = ttk.Style()
        style.configure("Phase.TLabel", padding=5, font=('Noto_Sans_CJK_TC_Regular', 10, 'bold'))
        style.configure("Status.TLabel", padding=5)
    
        # 設定文字標籤和顏色
        self.chat_display_tags = {
            "sender_user": {
                "font": ('Noto_Sans_CJK_TC_Regular', 10, 'bold'), 
                "foreground": "#2E7D32",  # 深綠色
                "spacing1": 10,  # 上方間距
                "spacing3": 5   # 下方間距
            },
            "sender_claude": {
                "font": ('Noto_Sans_CJK_TC_Regular', 10, 'bold'), 
                "foreground": "#1976D2",  # 深藍色
                "spacing1": 10,
                "spacing3": 5
            },
            "sender_system": {
                "font": ('Noto_Sans_CJK_TC_Regular', 10, 'bold'), 
                "foreground": "#757575",  # 灰色
                "spacing1": 10,
                "spacing3": 5
            },
            "message": {
                "font": ('Noto_Sans_CJK_TC_Regular', 10),
                "spacing1": 2,
                "spacing3": 10
            },
            "code": {
                "font": ('Noto_Serif_CJK_TC_Regular', 10),
                "background": "#F5F5F5",  # 淺灰色背景
                "spacing1": 5,
                "spacing3": 5
            },
            "timestamp": {
                "font": ('Noto_Sans_CJK_TC_Regular', 8),
                "foreground": "#9E9E9E"  # 淺灰色
            }
        }
        logging.debug("Styles setup completed")

    def _init_chat_area(self):
        """初始化聊天區域"""
        logging.debug("Initializing chat area")
        
        # 聊天區域框架
        chat_container = ttk.Frame(self.chat_frame)
        chat_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 聊天顯示區域
        self.chat_display = scrolledtext.ScrolledText(
            self.chat_frame,
            wrap=tk.WORD,
            font=self.chat_font
        )
        self.chat_display.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 設定文字標籤
        for tag, config in self.chat_display_tags.items():
            self.chat_display.tag_configure(tag, **config)
        
            # 輸入框架
        input_frame = ttk.Frame(self.chat_frame)
        input_frame.pack(fill=tk.X, padx=5, pady=5)
    
        # 添加控制框架（包含複選框和發送按鈕）
        control_frame = ttk.Frame(input_frame)
        control_frame.pack(fill=tk.X, expand=True)
        
        # 右鍵菜單
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="複製", command=self._copy_text)
        
        self.chat_display.bind("<Button-3>", self._show_context_menu)
        
        # 輸入區域框架
        input_container = ttk.Frame(self.chat_frame)
        input_container.pack(fill=tk.X, padx=10, pady=5)
        
        # 輸入區域
        self.input_area = scrolledtext.ScrolledText(
            control_frame,
            height=4,
            wrap=tk.WORD,
            font=self.chat_font
        )
        self.input_area.pack(fill=tk.X, expand=True, side=tk.LEFT, padx=(0, 5))
    
        # 右側控制區域
        right_control_frame = ttk.Frame(control_frame)
        right_control_frame.pack(side=tk.RIGHT, fill=tk.Y)
    
        # 添加複選框
        self.include_history = tk.BooleanVar(value=False)
        self.history_checkbox = ttk.Checkbutton(
            right_control_frame,
            text="與記錄對話",
            variable=self.include_history,
            command=self._on_history_toggle
        )
        self.history_checkbox.pack(side=tk.TOP, padx=5, pady=(0, 5))    
    
        # 添加滾動條
        input_scrollbar = ttk.Scrollbar(input_container, command=self.input_area.yview)
        self.input_area.configure(yscrollcommand=input_scrollbar.set)
    
        self.input_area.pack(fill=tk.X, expand=True, side=tk.LEFT, padx=(0, 5))
        input_scrollbar.pack(side=tk.LEFT, fill=tk.Y)
    
        # 移除所有默認的按鍵綁定
        for key in self.input_area.bind():
            self.input_area.unbind(key)
    
        # 只添加必要的按鍵綁定
        self.input_area.bind("<Return>", self._on_enter)
        #self.input_area.bind("<Key>", self._on_key)  # 添加按鍵處理
        
        # 發送按鈕
        self.send_button = ttk.Button(
            right_control_frame,
            text="Send",
            command=self._on_send
        )
        self.send_button.pack(side=tk.TOP, padx=5)
        
        # 綁定Enter鍵
        self.input_area.bind("<Return>", self._on_enter)
        logging.debug("Chat area initialization completed")

    def _on_history_toggle(self):
        """處理歷史記錄複選框狀態改變"""
        state = "開啟" if self.include_history.get() else "關閉"
        logging.debug(f"歷史記錄選項: {state}")

    def _collect_chat_history(self) -> str:
        """收集聊天歷史，特別處理代碼塊"""
        history = []
        content = self.chat_display.get("1.0", tk.END)
    
        import re
    
        # 匹配訊息的基本模式
        message_pattern = r'\[([\d:]+)\] (User|Claude|System):\n(.*?)(?=\n\[|$)'
        matches = re.finditer(message_pattern, content, re.DOTALL)
    
        for match in matches:
            timestamp, role, message = match.groups()
        
            # 過濾系統消息
            if role == 'System':
                if 'Processing' in message or 'Query completed' in message:
                    continue
        
            # 清理消息內容
            message = message.strip()
        
            # 跳過空消息
            if not message:
                continue
            
            if role in ['User', 'Claude']:
                # 處理消息中的代碼塊
                processed_message = self._process_code_blocks(message)
                formatted_message = f"[{timestamp}] {role}:\n{processed_message}\n\n"
                history.append(formatted_message)
    
        if history:
            return "Previous conversation:\n" + "".join(history)
        return ""

    def _process_code_blocks(self, message: str) -> str:
        """處理消息中的代碼塊"""
        import re
    
        # 檢測是否包含代碼塊
        code_block_pattern = r'```(?:\w+)?\n(.*?)```'
    
        def replace_code_block(match):
            """替換代碼塊為特殊格式"""
            code_content = match.group(1).strip()
            # 使用<CODE>標記包裝代碼，避免影響JSON解析
            return f"<CODE>\n{code_content}\n</CODE>"
    
        # 替換所有代碼塊
        processed_message = re.sub(code_block_pattern, replace_code_block, message, flags=re.DOTALL)
        return processed_message

    def _build_framework_prompt(self, query: str) -> str:
        """構建框架定義prompt，添加代碼處理說明"""
        base_prompt = f"""Please analyze the following query and design a thinking framework.
The framework MUST include analysis phases followed by an execution phase.
Note: Code blocks in the conversation history are wrapped in <CODE> tags.

Query: {query}

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
"""
        return base_prompt

    def _on_key(self, event):
        """處理按鍵輸入"""
        # 如果是Return鍵，讓_on_enter處理
        if event.keysym == "Return":
            return
    
        # 對於其他按鍵，確保它們能正常輸入
        return True  # 允許事件繼續傳播

    def _on_enter(self, event):
        """處理Enter鍵"""
        # Shift+Enter換行，Enter發送
        if not event.state & 0x1:  # 沒有按下Shift
            self._on_send()
            return 'break'  # 阻止默認行為
        return None  # 允許換行

    def _format_message(self, message: str) -> str:
        """格式化消息文本，保留所有特殊字符"""
        lines = message.split('\n')
        formatted_lines = []
        in_code_block = False
        code_block = []
    
        for line in lines:
            # 處理代碼塊標記
            if line.strip().startswith('```'):
                if in_code_block:
                    # 結束代碼塊
                    if code_block:
                        formatted_lines.append('\n'.join(code_block))
                    formatted_lines.append(line)  # 保留結束標記
                    code_block = []
                    in_code_block = False
                else:
                    # 開始代碼塊
                    formatted_lines.append(line)  # 保留開始標記
                    in_code_block = True
            elif in_code_block:
                code_block.append(line)
            else:
                formatted_lines.append(line)
    
        # 如果還有未處理的代碼塊
        if code_block:
            formatted_lines.append('\n'.join(code_block))
    
        return '\n'.join(formatted_lines)
        
    def _init_thinking_area(self):
        """初始化思考鏈區域"""
        logging.debug("Initializing thinking area")
        # 標題
        title_label = ttk.Label(
            self.thinking_frame,
            text="Thinking Chain Progress",
            font=('Noto_Sans_CJK_TC_Regular', 12, 'bold')
        )
        title_label.pack(fill=tk.X, padx=5, pady=5)
        
        # 思考鏈顯示區域
        self.thinking_display = scrolledtext.ScrolledText(
            self.thinking_frame,
            wrap=tk.WORD,
            font=self.chat_font
        )
        self.thinking_display.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 設定思考鏈文字標籤
        self.thinking_display.tag_configure("phase", font=('Noto_Sans_CJK_TC_Regular', 10, 'bold'))
        self.thinking_display.tag_configure("status", font=('Noto_Sans_CJK_TC_Regular', 10, 'italic'))
        self.thinking_display.tag_configure("content", font=('Courier', 10))
        logging.debug("Thinking area initialization completed")

    def _process_message(self, message: str):
        """處理用戶消息"""
        logging.info("Processing user message")
    
        # 禁用發送按鈕和輸入框
        self.send_button.config(state='disabled')
        self.input_area.config(state='disabled')
        self.history_checkbox.config(state='disabled')
    
        def run_thinking_chain():
            try:
                # 顯示處理中消息
                self.message_queue.put(("system", "Processing your query..."))
            
                # 如果需要包含歷史記錄
                if self.include_history.get():
                    history = self._collect_chat_history()
                    if history:
                        # 在prompt中說明代碼塊的處理方式
                        full_message = (
                            f"{history}\n"
                            "Note: Code blocks in the above history are wrapped in <CODE> tags.\n\n"
                            f"New query: {message}"
                        )
                        logging.debug(f"Complete message with history:\n{full_message}")
                    else:
                        full_message = message
                else:
                    full_message = message
            
                # 運行思考鏈
                results = self.thinking_chain.run(full_message)
            
                # 處理結果
                for result in results:
                    # 添加思考階段到UI
                    self.message_queue.put(("thinking", result))
                
                    # 如果有結論，添加到聊天區
                    if result.get('results') and result.get('results').get('content'):
                        self.message_queue.put(
                            ("claude", result['results']['content'])
                        )
            
                # 顯示使用量報告
                usage_report = self.api_handler.get_usage_report()
                report_msg = (
                    f"Query completed.\n"
                    f"Total tokens: {usage_report['usage']['total_tokens']}\n"
                    f"Estimated cost: ${usage_report['estimated_cost']:.4f}"
                )
                self.message_queue.put(("system", report_msg))
            
            except Exception as e:
                error_msg = f"Error processing message: {str(e)}"
                logging.error(error_msg)
                self.message_queue.put(("error", error_msg))
        
            finally:
                # 重新啟用控制項
                self.root.after(0, lambda: self.send_button.config(state='normal'))
                self.root.after(0, lambda: self.input_area.config(state='normal'))
                self.root.after(0, lambda: self.history_checkbox.config(state='normal'))
    
        # 在新線程中運行思考鏈
        threading.Thread(target=run_thinking_chain, daemon=True).start()

    def _process_message_queue(self):
        """處理消息隊列"""
        try:
            while True:
                msg_type, content = self.message_queue.get_nowait()
                
                if msg_type == "system":
                    self.system_message(content)
                elif msg_type == "claude":
                    self.add_message("Claude", content)
                elif msg_type == "thinking":
                    self.update_thinking_progress(content)
                elif msg_type == "error":
                    self.system_message(f"Error: {content}")
                    messagebox.showerror("Error", content)
                    
                self.message_queue.task_done()
                
        except queue.Empty:
            pass
        
        # 繼續檢查消息隊列
        self.root.after(100, self._process_message_queue)

    def _on_enter(self, event):
        """處理Enter鍵"""
        if not event.state & 0x1:  # 沒有按下Shift
            self._on_send()
            return 'break'

    def _on_send(self):
        """處理發送消息"""
        message = self.input_area.get("1.0", tk.END).strip()
        if message:
            logging.info(f"User message: {message}")
            self.add_message("User", message)
            self.input_area.delete("1.0", tk.END)
            self._process_message(message)

    def add_message(self, sender: str, message: str):
        """添加消息到聊天區域"""
        logging.debug(f"Adding message from {sender}")
        timestamp = datetime.now().strftime("%H:%M:%S")
    
        # 根據發送者選擇標籤
        if sender.lower() == "user":
            sender_tag = "sender_user"
        elif sender.lower() == "claude":
            sender_tag = "sender_claude"
        else:
            sender_tag = "sender_system"
    
        # 添加時間戳和發送者
        self.chat_display.insert(tk.END, f"[{timestamp}] ", "timestamp")
        self.chat_display.insert(tk.END, f"{sender}:\n", sender_tag)
    
        # 格式化並添加消息內容
        formatted_message = self._format_message(message)
        current_block = []
        in_code_block = False
    
        for line in formatted_message.split('\n'):
            # 檢測代碼塊標記
            if line.strip().startswith('```'):
                if current_block:
                    # 輸出之前累積的內容
                    block_content = '\n'.join(current_block)
                    tag = "code" if in_code_block else "message"
                    self.chat_display.insert(tk.END, f"{block_content}\n", tag)
                    current_block = []
            
                # 切換代碼塊狀態
                in_code_block = not in_code_block
                self.chat_display.insert(tk.END, f"{line}\n", "message")
            else:
                current_block.append(line)
    
        # 輸出最後累積的內容
        if current_block:
            block_content = '\n'.join(current_block)
            tag = "code" if in_code_block else "message"
            self.chat_display.insert(tk.END, f"{block_content}\n", tag)
    
        self.chat_display.insert(tk.END, "\n")
        self.chat_display.see(tk.END)
        
    def _copy_text(self):
        """複製選中的文本"""
        try:
            selected_text = self.chat_display.get(tk.SEL_FIRST, tk.SEL_LAST)
            self.root.clipboard_clear()
            self.root.clipboard_append(selected_text)
        except tk.TclError:
            pass  # 沒有選中文本
        
    def add_thinking_phase(self, phase_name: str, status: str, 
                          content: Optional[str] = None):
        """添加思考階段到思考鏈區域"""
        logging.debug(f"Adding thinking phase: {phase_name}")
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.thinking_display.insert(
            tk.END,
            f"[{timestamp}] Phase: {phase_name}\n",
            "phase"
        )
        self.thinking_display.insert(
            tk.END,
            f"Status: {status}\n",
            "status"
        )
        if content:
            self.thinking_display.insert(
                tk.END,
                f"Content:\n{content}\n",
                "content"
            )
        self.thinking_display.insert(tk.END, "\n")
        self.thinking_display.see(tk.END)
    
    def _format_thinking_results(self, results: dict) -> str:
        """格式化思考結果為人類可讀的形式"""
        output = []
    
        # 添加分析內容
        if 'content' in results:
            output.append("分析內容:")
            output.append(results['content'])
            output.append("")
    
        # 添加結論
        if 'conclusions' in results:
            output.append("結論:")
            for idx, conclusion in enumerate(results['conclusions'], 1):
                output.append(f"{idx}. {conclusion}")
            output.append("")
    
        # 添加品質檢查結果
        if 'quality_check' in results:
            qc = results['quality_check']
            output.append(f"品質評分: {qc.get('score', 0)}")
        
            if qc.get('score', 0) < 100:
                output.append("（系統將嘗試改進）")
        
            if 'issues' in qc and qc['issues']:
                output.append("\n待改進:")
                for idx, issue in enumerate(qc['issues'], 1):
                    output.append(f"{idx}. {issue}")
                
            if 'suggestions' in qc and qc['suggestions']:
                output.append("\n建議:")
                for idx, suggestion in enumerate(qc['suggestions'], 1):
                    output.append(f"{idx}. {suggestion}")
    
        return "\n".join(output)

    def update_thinking_progress(self, phase_data: dict):
        """更新思考鏈進度"""
        logging.debug(f"Updating thinking progress: {phase_data['name']}")
    
        try:
            # 準備顯示內容
            content = None
            if phase_data.get('results'):
                # 格式化結果為人類可讀的形式
                content = self._format_thinking_results(phase_data['results'])
        
            self.add_thinking_phase(
                phase_data['name'],
                phase_data['status'],
                content
            )
        except Exception as e:
            logging.error(f"Error updating thinking progress: {str(e)}")
            self.system_message(f"Error updating progress: {str(e)}")
    
    def add_thinking_phase(self, phase_name: str, status: str, 
                          content: Optional[str] = None):
        """添加思考階段到思考鏈區域"""
        logging.debug(f"Adding thinking phase: {phase_name}")
        timestamp = datetime.now().strftime("%H:%M:%S")
    
        # 轉換狀態文本
        status_map = {
            "pending": "等待中",
            "in_progress": "進行中",
            "complete": "完成",
            "failed": "失敗",
            "need_revision": "需要修改"
        }
        status_text = status_map.get(status, status)
    
        # 插入階段信息
        self.thinking_display.insert(
            tk.END,
            f"[{timestamp}] 階段: {phase_name}\n",
            "phase"
        )
        self.thinking_display.insert(
            tk.END,
            f"狀態: {status_text}\n",
            "status"
        )
        if content:
            self.thinking_display.insert(
                tk.END,
                f"內容:\n{content}\n",
                "content"
            )
        self.thinking_display.insert(tk.END, "\n")
        self.thinking_display.see(tk.END)
    
    def _show_context_menu(self, event):
        """顯示右鍵菜單"""
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def system_message(self, message: str):
        """顯示系統消息"""
        logging.info(f"System message: {message}")
        self.add_message("System", message)

def main():
    logging.info("Starting application")
    try:
        root = tk.Tk()
        app = ChatUI(root)
        logging.info("Application initialized successfully")
        root.mainloop()
    except Exception as e:
        logging.error(f"Application error: {str(e)}")
        raise

if __name__ == "__main__":
    main()