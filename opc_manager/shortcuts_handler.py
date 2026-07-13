"""
Apple Shortcuts Integration Handler for OPC-Agents v0.3.27

Provides 5 shortcut actions callable from macOS Shortcuts app:
1. quick_task      - Execute a quick task via LLM
2. query_status     - Query today's task/deliverable status
3. create_deliverable - Create a deliverable record
4. record_income    - Record an income entry
5. daily_report     - Generate today's daily summary report

Usage from Shortcuts (Run Shell Script):
    python -m opc_manager.shortcuts_handler quick_task "帮我写一封客户跟进邮件"
    python -m opc_manager.shortcuts_handler query_status
    python -m opc_manager.shortcuts_handler create_deliverable --title "周报" --type "report"
    python -m opc_manager.shortcuts_handler record_income --amount 5000 --client "张三" --source "咨询费"
    python -m opc_manager.shortcuts_handler daily_report
"""

import sys
import json
import argparse
from datetime import datetime
from typing import Any, Optional


class ShortcutResult:
    """Standardized result format for Shortcuts consumption."""

    def __init__(
        self, success: bool, message: str, data: Optional[dict[Any, Any]] = None
    ):
        self.success = success
        self.message = message
        self.data = data or {}

    def to_shortcuts_output(self) -> str:
        """Format output for Apple Shortcuts display."""
        if self.success:
            return f" {self.message}"
        else:
            return f" {self.message}"

    def to_json(self) -> str:
        return json.dumps(
            {
                "success": self.success,
                "message": self.message,
                "data": self.data,
                "timestamp": datetime.now().isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        )


class ShortcutsHandler:
    """Handles Apple Shortcuts actions for OPC-Agents."""

    def __init__(self) -> None:
        self._init_components()

    def _init_components(self) -> None:
        """Lazy-initialize required components."""
        from opc_manager.settings import get_settings
        from opc_manager.data_manager import init_db

        self.settings = get_settings()
        init_db()

    def quick_task(self, task_text: str) -> ShortcutResult:
        """
        Action 1: Quick Task Execution
        Input: Task description text
        Output: LLM-generated result or error

        Example: quick_task "帮我写一封客户跟进邮件"
        """
        if not task_text or not task_text.strip():
            return ShortcutResult(False, "任务内容不能为空")

        try:
            from opc_manager.simple_llm_service import SimpleLLMService

            llm = SimpleLLMService()

            prompt = f"""你是一个专业的AI助手。请完成以下任务，直接给出结果：

任务：{task_text}

要求：
- 直接输出结果，不要解释过程
- 如果需要结构化信息，使用清晰的格式
- 保持简洁专业"""

            response = llm.complete(prompt)

            if response and response.strip():
                return ShortcutResult(
                    True,
                    f"任务完成:\n{response[:500]}",
                    {
                        "action": "quick_task",
                        "input_length": len(task_text),
                        "output_length": len(response),
                    },
                )
            else:
                return ShortcutResult(False, "AI未返回有效结果")

        except Exception as e:
            return ShortcutResult(False, f"执行失败: {str(e)}")

    def query_status(self) -> ShortcutResult:
        """
        Action 2: Query Today's Status
        Output: Today's tasks completed, income recorded

        Example: query_status
        """
        try:
            from opc_manager.data_manager import execute_query

            today = datetime.now().strftime("%Y-%m-%d")

            tasks = execute_query(
                "SELECT COUNT(*) as count FROM tasks WHERE DATE(created_at)=?", (today,)
            )
            income_rows = execute_query(
                "SELECT COALESCE(SUM(amount), 0) as total FROM finance_records WHERE type='income' AND DATE(date)=?",
                (today,),
            )

            t_count = tasks[0]["count"] if tasks else 0
            i_total = income_rows[0]["total"] if income_rows else 0

            status_msg = (
                f" 今日状态 ({today})\n"
                f"━━━━━━━━━━━━━━━━\n"
                f" 任务数: {t_count}\n"
                f" 收入总计: ¥{i_total:,.0f}\n"
                f"━━━━━━━━━━━━━━━━"
            )

            return ShortcutResult(
                True,
                status_msg,
                {"date": today, "tasks": t_count, "income": float(i_total)},
            )

        except Exception as e:
            return ShortcutResult(False, f"查询失败: {str(e)}")

    def create_deliverable(
        self, title: str, dtype: str = "document", content: str = ""
    ) -> ShortcutResult:
        """
        Action 3: Create Deliverable Record
        Params: --title (required), --type (default: document), --content (optional)

        Creates a task record tagged as a deliverable.

        Example: create_deliverable --title "Q2报告" --type "report"
        """
        if not title or not title.strip():
            return ShortcutResult(False, "成果物标题不能为空")

        try:
            from opc_manager.data_manager import execute_write, gen_id

            did = gen_id()
            now = datetime.now().isoformat()

            execute_write(
                "INSERT INTO tasks (id, title, description, status, tags, created_at) VALUES (?,?,?,?,?,?)",
                (did, title, content or "", "done", f"deliverable:{dtype}", now),
            )

            type_labels = {
                "document": "文档",
                "report": "报告",
                "proposal": "方案",
                "invoice": "发票",
            }
            label = type_labels.get(dtype, "文件")

            return ShortcutResult(
                True,
                f"{label}已创建: {title}\nID: {did[:8]}",
                {"id": did, "title": title, "type": dtype},
            )

        except Exception as e:
            return ShortcutResult(False, f"创建失败: {str(e)}")

    def record_income(
        self, amount: float, client: str = "", source: str = ""
    ) -> ShortcutResult:
        """
        Action 4: Record Income Entry
        Params: --amount (required), --client, --source

        Example: record_income --amount 5000 --client "张三" --source "咨询费"
        """
        if not amount or amount <= 0:
            return ShortcutResult(False, "金额必须大于0")

        try:
            from opc_manager.data_manager import execute_write, gen_id

            iid = gen_id()
            today = datetime.now().strftime("%Y-%m-%d")
            now = datetime.now().isoformat()

            execute_write(
                "INSERT INTO finance_records "
                "(id, type, amount, category, source, date, note, created_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    iid,
                    "income",
                    amount,
                    source or "其他",
                    source or "其他",
                    today,
                    client or "未知客户",
                    now,
                ),
            )

            return ShortcutResult(
                True,
                f" 收入已记录\n金额: ¥{amount:,.0f}\n客户: {client or '未知'}\n来源: {source or '其他'}",
                {"id": iid, "amount": amount, "client": client, "date": today},
            )

        except Exception as e:
            return ShortcutResult(False, f"记录失败: {str(e)}")

    def daily_report(self) -> ShortcutResult:
        """
        Action 5: Generate Daily Summary Report
        Output: Today's comprehensive summary

        Example: daily_report
        """
        try:
            from opc_manager.data_manager import execute_query

            today = datetime.now().strftime("%Y-%m-%d")

            tasks = execute_query(
                "SELECT * FROM tasks WHERE DATE(created_at)=? ORDER BY created_at DESC LIMIT 10",
                (today,),
            )
            income_rows = execute_query(
                "SELECT * FROM finance_records WHERE type='income' AND DATE(date)=? ORDER BY date DESC",
                (today,),
            )
            deliverable_tasks = execute_query(
                "SELECT * FROM tasks WHERE tags LIKE 'deliverable:%' "
                "AND DATE(created_at)=? ORDER BY created_at DESC LIMIT 5",
                (today,),
            )

            total_income = sum((r.get("amount") or 0) for r in income_rows)

            report = (
                f" OPC-Agent 日报 ({today})\n"
                f"{'='*30}\n\n"
                f" 今日收入: ¥{total_income:,.0f}\n"
                f"   共 {len(income_rows)} 笔记录\n\n"
                f" 今日成果: {len(deliverable_tasks)} 项\n"
            )

            if deliverable_tasks:
                for d in deliverable_tasks[:5]:
                    tag = d.get("tags", "")
                    dtype = (
                        tag.replace("deliverable:", "")
                        if tag.startswith("deliverable:")
                        else "?"
                    )
                    report += f"   • [{dtype}] {d.get('title', '')}\n"

            report += f"\n 近期任务: {len(tasks)} 条\n"

            if tasks:
                for t in tasks[:5]:
                    status = "" if t.get("status") == "done" else ""
                    report += (
                        f"   {status} {t.get('title', t.get('description', ''))[:40]}\n"
                    )

            report += f"\n{'='*30}\n由 OPC-Agents 自动生成 "

            return ShortcutResult(
                True,
                report,
                {
                    "date": today,
                    "income_total": total_income,
                    "deliverable_count": len(deliverable_tasks),
                    "task_count": len(tasks),
                },
            )

        except Exception as e:
            return ShortcutResult(False, f"生成日报失败: {str(e)}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="OPC-Agents Apple Shortcuts Handler",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m opc_manager.shortcuts_handler quick_task "写一封邮件"
  python -m opc_manager.shortcuts_handler query_status
  python -m opc_manager.shortcuts_handler record_income --amount 5000 --client "张三"
        """,
    )

    subparsers = parser.add_subparsers(dest="action", help="Available actions")

    p1 = subparsers.add_parser("quick_task", help="Execute a quick AI task")
    p1.add_argument("text", help="Task description")

    subparsers.add_parser("query_status", help="Query today's status summary")

    p3 = subparsers.add_parser("create_deliverable", help="Create a new deliverable")
    p3.add_argument("--title", required=True, help="Deliverable title")
    p3.add_argument(
        "--type", default="document", help="Type: document/report/proposal/invoice"
    )
    p3.add_argument("--content", default="", help="Content text")

    p4 = subparsers.add_parser("record_income", help="Record an income entry")
    p4.add_argument("--amount", type=float, required=True, help="Income amount")
    p4.add_argument("--client", default="", help="Client name")
    p4.add_argument("--source", default="", help="Income source")

    subparsers.add_parser("daily_report", help="Generate daily summary report")

    args = parser.parse_args()

    if not args.action:
        parser.print_help()
        sys.exit(1)

    handler = ShortcutsHandler()

    actions = {
        "quick_task": lambda: handler.quick_task(args.text),
        "query_status": lambda: handler.query_status(),
        "create_deliverable": lambda: handler.create_deliverable(
            args.title, args.type, args.content
        ),
        "record_income": lambda: handler.record_income(
            args.amount, args.client, args.source
        ),
        "daily_report": lambda: handler.daily_report(),
    }

    result = actions[args.action]()
    print(result.to_shortcuts_output())

    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
