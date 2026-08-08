import pathlib
import json
import datetime
import sys
import requests
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich import box

console = Console(force_terminal=True, color_system="standard", legacy_windows=False)

sys.stdout.reconfigure(encoding='utf-8')

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "qwen2.5:7b"

home_dir = Path.home()
log_folder = home_dir / ".nudge"
log_folder.mkdir(parents=True, exist_ok=True)
log_file = log_folder / "log.jsonl"
chat_file = log_folder / "last_context.jsonl"

def explain_failure(command_text, exit_code, context_text):
    prompt = (
        f"""The user ran this command: {command_text} It failed with exit code{exit_code}.Here is the recent terminal output:{context_text} In 2-3 short sentences, explain what went wrong. If the output doesn't clearly show the cause, say so rather than guessing.Then, on its own separate line, write a fix using this exact format, with no markdown, no bold text, no backticks, and no code blocks:FIX: <the corrected command>Only write an actual command on the FIX line if you are genuinely confident about the exact correction. If you are not fully confident, or there is no simple one-line fix, write exactly:FIX: noneExample of the correct format:The command "gt status" was not recognized. It looks like a typo of the git command "git status", missing the "i" in git.FIX: git status. Be 100% sure that the  FIX is its own, new line"""
    )

    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": 100
        },
        "keep_alive": "30m"
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()

        text = result.get("response", "(no response text returned)")
        data = {
            "response": text,
            "command": command_text,
            "exit_code": exit_code,
            "context_text": context_text
        }

        try:
            json_string = json.dumps(data, sort_keys=True, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            console.print(f"Error converting dictionary to JSON: {e}")
            json_string = None

        if json_string:
            with chat_file.open("a") as f:
                f.write(json_string + "\n")

        lines = text.splitlines()
        cleaned_lines = []
        extracted_fix = None

        for line in lines:
            if line.startswith("FIX:"):
                extracted_fix = line.split("FIX:", 1)[1].strip()
            else:
                cleaned_lines.append(line)

        panel_content = "\n".join(cleaned_lines).strip()

        if extracted_fix and extracted_fix.strip().lower() != "none":
            panel_content += f"\n\n[yellow]FIX:[/yellow] [bold green]{extracted_fix}[/bold green]"

        explanation_panel = Panel(
            panel_content,
            title="AI Explanation",
            border_style="cyan",
            box=box.ROUNDED
        )
        console.print(explanation_panel)

    except requests.exceptions.RequestException as e:
        console.print(f"(Could not reach local AI model: {e})")

def log_failure(command_text, exit_code, context_file=None):
    now = datetime.datetime.now()
    data = {
        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
        "command": command_text,
        "exit_code": exit_code
    }

    try:
        json_string = json.dumps(data, sort_keys=True, ensure_ascii=False)
    except (TypeError, ValueError) as e:
        console.print(f"Error converting dictionary to JSON: {e}")
        json_string = None

    if json_string:
        with log_file.open("a") as f:
            f.write(json_string + "\n")

    context_text = ""
    if context_file:
        context_path = Path(context_file)
        if context_path.exists():
            context_text = context_path.read_text(errors="ignore")

    explain_failure(command_text, exit_code, context_text)

def last_fail():
    if not log_file.exists():
        console.print("No failures logged yet!")
        return

    with log_file.open("r") as f:
        lines = f.readlines()

    if lines:
        last_line = lines[-1]
        log_data = json.loads(last_line)
        console.print("--- Last Run Log ---")
        console.print(f"Command   : {log_data.get('command')}")
        console.print(f"Exit Code : {log_data.get('exit_code')}")
        console.print(f"Timestamp : {log_data.get('timestamp')}")
        console.print("--------------------")

def start_chat():
    if chat_file.is_file():
        with chat_file.open("r") as f:
            lines = f.readlines()

        if lines:
            last_line = lines[-1]
            chat_data = json.loads(last_line)
        else:
            console.print("No recent failures to chat about!", style="bold yellow")
            return

        original_command = chat_data.get("command", "unknown command")
        original_context = chat_data.get("context_text", "")
        original_response = chat_data.get("response", "")

        messages = [
            {"role": "system", "content": "You are a terminal assistant helping debug a command failure. Keep answers concise and avoid markdown formatting."},
            {"role": "user", "content": f"I ran this command: {original_command}. It failed with this terminal output:\n{original_context}"},
            {"role": "assistant", "content": original_response}
        ]

        console.print(f'Beginning chat. Issue, command failed: [red]{chat_data.get("command")}[/red]', style="bold yellow")

        while True:
            question = input("You: ")
            if question != "" and question.lower() != "exit" and question.lower() != "quit":
                messages.append({"role": "user", "content": question})
                try:
                    with console.status("Thinking...", spinner="dots"):
                        payload = {
                            "model": MODEL_NAME,
                            "messages": messages,
                            "stream": False,
                            "options": {
                                "num_predict": 100
                            }
                        }

                        response = requests.post(OLLAMA_CHAT_URL, json=payload, timeout=30)
                        response.raise_for_status()
                        result = response.json()

                        text = result["message"]["content"]
                        chat_panel = Panel(
                            text,
                            title="Nudge",
                            border_style="magenta",
                            box=box.ROUNDED
                        )
                        console.print(chat_panel)
                        messages.append({"role": "assistant", "content": text})
                except requests.exceptions.RequestException as e:
                    console.print(f"(Could not reach local AI model: {e})")
            else:
                break
    else:
        console.print("No recent failures to chat about!", style="bold yellow")

if __name__ == "__main__":
    user_args = sys.argv[1:]

    if not user_args:
        console.print("You did not type anything after 'python nudge.py'!")
    else:
        first_word = user_args[0]
        if first_word == "log-failure":
            command_arg = user_args[1]
            exit_code_arg = user_args[2]
            context_file_arg = user_args[3] if len(user_args) > 3 else None
            log_failure(command_arg, exit_code_arg, context_file_arg)
        elif first_word == 'last_fail':
            last_fail()
        elif first_word == "chat":
            start_chat()