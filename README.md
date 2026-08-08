# Nudge

A PowerShell profile add-on that watches for failed commands in your terminal and automatically explains what went wrong, using a local LLM via [Ollama](https://ollama.com), so nothing ever leaves your machine.

## Features

- Automatically detects failed commands and explains them in plain language
- Suggests a corrected command when it's confident about the fix
- Skips known-noisy failures (configurable ignore list)
- Follow-up chat mode to dig deeper into a specific failure
- Fast, local, and works offline, no API keys, no cloud calls

## Prerequisites

- Windows with PowerShell
- [Python 3](https://www.python.org/) with `pip`
- [Ollama](https://ollama.com) installed and running, with a model pulled (e.g. `ollama pull qwen2.5:7b`)
- Git (for the branch info shown in the prompt)

## Setup

1. Clone this repo somewhere on your machine:

```powershell
   git clone https://github.com/TheCanadianEngineer/Nudge.git
```

2. Install the Python dependencies:

```powershell
   pip install requests rich
```

3. Add this line to your PowerShell `$PROFILE` (find its path by running `$PROFILE`, create the file if it doesn't exist):

```powershell
   . "C:\path\to\Nudge\nudge-profile.ps1"
```

4. Open a fresh terminal window.

## Usage

Just use your terminal normally. When a command fails, Nudge automatically checks it and prints an explanation.

| Command     | What it does                                          |
| ----------- | ----------------------------------------------------- |
| `chat`      | Start a follow-up conversation about the last failure |
| `lastfail`  | Show the last logged failure                          |
| `nudgeoff`  | Turn off automatic checks for this session            |
| `nudgeon`   | Turn automatic checks back on                         |
| `nudgehelp` | List all available commands                           |

While a check is running, press **Enter** at any time to skip it.

## How it works

The PowerShell profile hooks into the prompt render cycle to detect failed commands, captures the relevant terminal output, and hands it off to a small Python script (`nudge.py`), which sends it to a locally running Ollama model and prints the response back into your terminal.

## Configuration

Edit these variables near the top of `nudge-profile.ps1`:

- `$script:ignoredCommands`, commands to never check (default: `grep`, `findstr`, `robocopy`)

And in `nudge.py`:

- `MODEL_NAME`, which Ollama model to use

## License

MIT (or your preferred license, add a `LICENSE` file if you want one)
