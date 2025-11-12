# -*- coding: utf-8 -*-
import os
import shlex
import json
import subprocess
import dotenv
from datetime import datetime
from typing import TypedDict, Optional, List, Dict, Any

from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI  # 任意のプロバイダに置換可（model名だけ合わせる）
from langchain.messages import ToolMessage

dotenv.load_dotenv()

# ----------------------------------
# 0) 実行フラグ（まずは生成のみ→安全）
# ----------------------------------
EXECUTE_COMMAND = True

# ----------------------------------
# 1) Taskwarrior CLI ラッパ
# ----------------------------------
def tw(*args: str) -> subprocess.CompletedProcess:
    """
    Taskwarrior を実行する薄いラッパ。環境変数 TASK_WARRIOR_PATH が未設定なら 'task' を PATH から探す。
    """
    task_path = os.environ.get("TASK_WARRIOR_PATH", "task")
    return subprocess.run(
        [task_path] + list(args),
        capture_output=True,
        text=True,
        check=False,
    )

# ----------------------------------
# 2) Taskwarriorの“コンテキスト”（使い方ガイド）
# ----------------------------------
TASKWARRIOR_GUIDE = r"""
Usage: task                                                   Runs rc.default.command, if specified.
       task <filter> active                                   Active tasks
       task          add <mods>                               Adds a new task
       task <filter> all                                      All tasks
       task <filter> annotate <mods>                          Adds an annotation to an existing task
       task <filter> append <mods>                            Appends text to an existing task description
       task <filter> blocked                                  Blocked tasks
       task <filter> blocking                                 Blocking tasks
       task <filter> burndown.daily                           Shows a graphical burndown chart, by day
       task <filter> burndown.monthly                         Shows a graphical burndown chart, by month
       task <filter> burndown.weekly                          Shows a graphical burndown chart, by week
       task          calc <expression>                        Calculator
       task          calendar [due|<month> <year>|<year>] [y] Shows a calendar, with due tasks marked
       task          colors [sample | legend]                 All colors, a sample, or a legend
       task          columns [substring]                      All supported columns and formatting styles
       task          commands                                 Generates a list of all commands, with behavior details
       task <filter> completed                                Completed tasks
       task          config [name [value | '']]               Change settings in the task configuration
       task          context [<name> | <subcommand>]          Set and define contexts (default filters / modifications)
       task <filter> count                                    Counts matching tasks
       task <filter> delete <mods>                            Deletes the specified task
       task <filter> denotate <pattern>                       Deletes an annotation
       task          diagnostics                              Platform, build and environment details
       task <filter> done <mods>                              Marks the specified task as completed
       task <filter> duplicate <mods>                         Duplicates the specified tasks
       task <filter> edit                                     Launches an editor to modify a task directly
       task          execute <external command>               Executes external commands and scripts
       task <filter> export [<report>]                        Exports tasks in JSON format
       task <filter> ghistory.annual                          Shows a graphical report of task history, by year
       task <filter> ghistory.daily                           Shows a graphical report of task history, by day
       task <filter> ghistory.monthly                         Shows a graphical report of task history, by month
       task <filter> ghistory.weekly                          Shows a graphical report of task history, by week
       task          help ['usage']                           Displays this usage help text
       task <filter> history.annual                           Shows a report of task history, by year
       task <filter> history.daily                            Shows a report of task history, by day
       task <filter> history.monthly                          Shows a report of task history, by month
       task <filter> history.weekly                           Shows a report of task history, by week
       task <filter> ids                                      Shows the IDs of matching tasks, as a range
       task          import [<file> ...]                      Imports JSON files
       task          import-v2                                Imports Taskwarrior v2.x files
       task <filter> information                              Shows all data and metadata
       task <filter> list                                     Most details of tasks
       task          log <mods>                               Adds a new task that is already completed
       task          logo                                     Displays the Taskwarrior logo
       task <filter> long                                     All details of tasks
       task <filter> ls                                       Few details of tasks
       task <filter> minimal                                  Minimal details of tasks
       task <filter> modify <mods>                            Modifies the existing task with provided arguments.
       task <filter> newest                                   Newest tasks
       task          news                                     Displays news about the recent releases
       task <filter> next                                     Most urgent tasks
       task <filter> oldest                                   Oldest tasks
       task <filter> overdue                                  Overdue tasks
       task <filter> prepend <mods>                           Prepends text to an existing task description
       task <filter> projects                                 Shows all project names used
       task <filter> purge                                    Removes the specified tasks from the data files. Causes permanent
                                                              loss of data.
       task <filter> ready                                    Most urgent actionable tasks
       task <filter> recurring                                Recurring Tasks
       task          reports                                  Lists all supported reports
       task          show [all | substring]                   Shows all configuration variables or subset
       task <filter> start <mods>                             Marks specified task as started
       task <filter> stats                                    Shows task database statistics
       task <filter> stop <mods>                              Removes the 'start' time from a task
       task <filter> summary                                  Shows a report of task status by project
       task          synchronize [initialize]                 Synchronizes data with the Taskserver
       task <filter> tags                                     Shows a list of all tags used
       task [filter] timesheet                                Summary of completed and started tasks
       task          udas                                     Shows all the defined UDA details
       task <filter> unblocked                                Unblocked tasks
       task          undo                                     Reverts the most recent change to a task
       task <filter> uuids                                    Shows the UUIDs of matching tasks, as a space-separated list
       task          version                                  Shows the Taskwarrior version number
       task <filter> waiting                                  Waiting (hidden) tasks
       task          _aliases                                 Generates a list of all aliases, for autocompletion purposes
       task          _columns                                 Displays only a list of supported columns
       task          _commands                                Generates a list of all commands, for autocompletion purposes
       task          _config                                  Lists all supported configuration variables, for completion
                                                              purposes
       task          _context                                 Lists all supported contexts, for completion purposes
       task          _get <DOM> [<DOM> ...]                   DOM Accessor
       task <filter> _ids                                     Shows the IDs of matching tasks, in the form of a list
       task <filter> _projects                                Shows only a list of all project names used
       task          _show                                    Shows all configuration settings in a machine-readable format
       task <filter> _tags                                    Shows only a list of all tags used, for autocompletion purposes
       task          _udas                                    Shows the defined UDAs for completion purposes
       task <filter> _unique <attribute>                      Generates lists of unique attribute values
       task <filter> _urgency                                 Displays the urgency measure of a task
       task <filter> _uuids                                   Shows the UUIDs of matching tasks, as a list
       task          _version                                 Shows only the Taskwarrior version number
       task          _zshattributes                           Generates a list of all attributes, for zsh autocompletion
                                                              purposes
       task          _zshcommands                             Generates a list of all commands, for zsh autocompletion purposes
       task <filter> _zshids                                  Shows the IDs and descriptions of matching tasks
       task <filter> _zshuuids                                Shows the UUIDs and descriptions of matching tasks

       burndown                                               Aliased to 'burndown.weekly'
       ghistory                                               Aliased to 'ghistory.monthly'
       history                                                Aliased to 'history.monthly'
       rm                                                     Aliased to 'delete'
"""

# ----------------------------------
# 3) ツール：出力を固定化（JSONコンテナ）
# ----------------------------------
class CommandSpec(TypedDict):
    command: str   # 例: task add "企画書ドラフト" due:fri +work priority:M assignee:U123
    reason: str    # どう解釈してこのコマンドになったか

@tool("emit_command", return_direct=True)
def emit_command(cmd: str, reason: Optional[str] = None) -> CommandSpec:
    """
    最終出力コンテナ。モデルはこのツールを1回だけ呼ぶ。
    ここでは生成のみ。実行は run() 側でフラグに応じて行う。
    """
    return {"command": cmd.strip(), "reason": (reason or "").strip()}

# ----------------------------------
# 4) システムプロンプト
# ----------------------------------
SYSTEM_PROMPT = f"""
あなたは Taskwarrior コマンド作成アシスタントです。
ユーザーの自然文を Taskwarrior コマンドに安全に正規化してください。

# コンテキスト（リファレンス）
{TASKWARRIOR_GUIDE}

# 重要ルール
- 出力は必ず tool `emit_command` を1回だけ実行して返すこと。
- 返すのは “実行可能な1行のコマンド” と、その短い理由（日本語）。
- 不明点があっても推測で安全側に寄せる（例: 期日が「金曜」だけなら due:fri を使う）。
- タグは `+tag` 形式、優先度は `priority:H|M|L`。期日は `due:`。担当は `assignee:`。
- すでにIDが明示されている操作（done/modify/assign）は ID をそのまま使う。
- 実行はしない（生成のみ）。壊れる可能性のある曖昧パラメータは避ける（不必要な削除などは出さない）。
"""

# ----------------------------------
# 5) エージェント生成
# ----------------------------------
llm = ChatOpenAI(model="gpt-5-mini", temperature=0)

agent = create_agent(
    model=llm,
    tools=[emit_command],
    system_prompt=SYSTEM_PROMPT,
)

# ----------------------------------
# 6) 実行ラッパ（生成→必要なら即実行）
# ----------------------------------
def run(query: str) -> Dict[str, Any]:
    """
    自然文 -> emit_command(JSON) を得て、
    EXECUTE_COMMAND=True の場合は Taskwarrior を実行して結果を返す。
    """
    res = agent.invoke({"messages": [{"role": "user", "content": query}]})
    # create_agent の戻り shape は実装で差があるが、emit_command(return_direct=True) なら
    # 通常 res は dict(CommandSpec) か、それに準ずる content を持つ
    if isinstance(res, dict) and "command" in res:
        cmd = res["command"]
        reason = res.get("reason", "")
    else:
        # 念のためフォールバック（content 側に dict が入ってくる実装もある）
        maybe = getattr(res, "content", res)
        for message in maybe["messages"]:
            if isinstance(message, ToolMessage):
                payload = json.loads(message.content)
                cmd = payload.get("command", "")
                reason = payload.get("reason", "")

    out: Dict[str, Any] = {"generated": {"command": cmd, "reason": reason}}

    if EXECUTE_COMMAND:
        # 引用を考慮して shlex.split
        args = shlex.split(cmd)
        print(args)
        proc = tw(*args[1:])
        out["exec"] = {
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
    return out

# ----------------------------------
# 7) 簡易テスト
# ----------------------------------
if __name__ == "__main__":
    tests: List[str] = [
        "金曜までに『競合調査メモ』を @alice に振って。タグは #research",
        "今の自分のタスク見せて",
        "請求のやつ探して",
        "ID 42 を完了にして",
        "ID 98 の期日を来週月曜に変更して",
    ]
    for q in tests:
        result = run(q)
