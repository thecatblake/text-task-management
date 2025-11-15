# -*- coding: utf-8 -*-
import os
import shlex
import json
import subprocess
import dotenv
from typing import Dict, Any

from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver  

dotenv.load_dotenv()

# ----------------------------------
# Taskwarrior CLI ラッパ
# ----------------------------------
def tw(*args: str) -> subprocess.CompletedProcess:
    task_path = os.environ.get("TASK_WARRIOR_PATH", "task")

    base = [
        task_path,
        "rc.confirmation=off",
        "rc.recurrence.confirmation=off",
        "rc.dependency.confirmation=off",
        "rc.bulk=0",
    ]

    return subprocess.run(
        base + list(args),
        capture_output=True,
        text=True,
        check=False,
    )


# ----------------------------------
# Taskwarriorの“コンテキスト”（使い方ガイド）
#   → プロンプト内で参照するだけ
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
       task          _udas                                    Shows all the defined UDA details, for completion purposes
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
# ツール定義
# ----------------------------------

@tool("task_export")
def task_export(filter_: str = "") -> str:
    """
    Taskwarrior のタスクを JSON で取得する。
    filter_ には通常のフィルタ式（例: 'status:pending', 'id.not:7' など）を入れる。
    戻り値は JSON 文字列（配列）。
    """
    args = []
    if filter_:
        args.append(filter_)
    args += ["export"]

    proc = tw(*args)
    return proc.stdout  # JSON

DANGEROUS_SUBSTRINGS = [" purge", " rm ", " synchronize", " import-v2"]

@tool("task_cli")
def task_cli(cmd: str) -> str:
    """
    任意の Taskwarrior コマンドを実行する。
    ただし、極端に破壊的な操作（purge 等）はブロックする。
    """
    for bad in DANGEROUS_SUBSTRINGS:
        if bad in cmd:
            return f"ERROR: dangerous command blocked: {cmd}"

    args = shlex.split(cmd)
    if args and args[0] == "task":
        args = args[1:]

    proc = tw(*args)
    return proc.stdout or proc.stderr

@tool("task_run")
def task_run(cmd: str) -> str:
    """
    Taskwarrior コマンドを実行して、その結果を JSON 文字列で返す。
    """
    args = shlex.split(cmd)
    if args and args[0] == "task":
        args = args[1:]

    proc = tw(*args)
    result = {
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }
    return json.dumps(result, ensure_ascii=False)

# ----------------------------------
# システムプロンプト
# ----------------------------------
SYSTEM_PROMPT = f"""
あなたは、ユーザーのタスク管理を手伝う「人間のアシスタント」です。
裏側では Taskwarrior を使いますが、そのことは一切ユーザーに悟られてはいけません。

あなたは次のツールを使えます:

- task_export(filter_: str = "")
  - タスクを JSON で取得するために使います。
- task_cli(cmd: str)
  - 状態確認など、補助的に使って構いません。
- task_run(cmd: str)
  - 実際に操作を行いたいときに使います。
  - 戻り値の JSON に stdout / stderr / returncode が入っています。

# コンテキスト（リファレンス）
{TASKWARRIOR_GUIDE}

# 重要ルール
- ユーザーの依頼を理解したら、
  - 必要に応じて task_export などで現在のタスク状態を確認し、
  - 実際に操作が必要な場合は task_run を呼んでください。
- その後、ツールの結果（タスク一覧やエラー内容）を読み取り、
  最後は「人間のアシスタント」として自然な日本語でユーザーに説明して終了してください。
- ユーザーには「Taskwarrior」「コマンド」「CLI」「stdout」「stderr」などの単語は一切見せてはいけません。
- 行数が多いタスク一覧は、そのまま貼らずに要約してください。
- 危険そうな操作（一括削除など）の場合は、
  実行前に task_export で対象を確認し、必要ならユーザーに確認する文言を含めてください。
"""

# ----------------------------------
# エージェント生成
# ----------------------------------
llm = ChatOpenAI(model="gpt-5-mini", temperature=0)

agent = create_agent(
    model=llm,
    tools=[task_export, task_cli, task_run],
    system_prompt=SYSTEM_PROMPT,
    checkpointer=InMemorySaver(),
)

# ----------------------------------
# エントリポイント
# ----------------------------------
def run(query: str) -> Dict[str, Any]:
    """
    自然文 -> agent（内部で task_export / task_run などを実行）
            -> 人間向けの返答をそのまま返す
    """
    res = agent.invoke(
        {"messages": [{"role": "user", "content": query}]},
        {"configurable": {"thread_id": "1"}}
    )

    # create_agent はだいたい {"messages": [...]} を返す。
    # 最後の AIMessage の content をユーザー向け返答として扱う。
    if isinstance(res, dict) and "messages" in res:
        msgs = res["messages"]
        if msgs:
            reply = getattr(msgs[-1], "content", "") or ""
        else:
            reply = ""
    else:
        reply = getattr(res, "content", str(res))

    return {"reply": reply}


if __name__ == "__main__":
    while True:
        q = input("msg: ")
        if not q:
            continue
        result = run(q)
        print("--- REPLY ---")
        print(result["reply"])
