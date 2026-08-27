<div align="center">

# OpenInstinct

### Your own AI assistant that is always on

Text it a task. It can use a real browser, search the live web, work with files, run tools, remember your conversations, and text you back when it is done.

**Always on** · **Real browser** · **Private workspace** · **Open source**

</div>

<video src="https://github.com/user-attachments/assets/16968273-2fe1-4c25-ae89-a7a9413e4a72" width="100%" controls autoplay loop muted></video>

<p align="center"><em>Real demo: one text starts live research and the answer comes back in the conversation.</em></p>

## What can it do?

| | OpenInstinct can... |
| --- | --- |
| 🌐 **Use a real browser** | Open websites, click through pages, fill forms, download things, and stay signed in for next time. |
| 🔎 **Research the live web** | Find current information, compare options, check sources, and send you a useful answer. |
| 📁 **Work with your files** | Read, write, organize, and turn documents, notes, reports, and spreadsheets into finished work. |
| 🛠️ **Use tools and run tasks** | Install what it needs, run commands, test its work, fix problems, and keep going until the job is done. |
| 🧠 **Remember your conversations** | Keep each person's conversation separate, save useful context, and pick up where you left off after a restart. |
| 🤝 **Bring in extra help** | Split a bigger job between smaller AI helpers, then bring the result back into one clear reply. |
| 💬 **Talk where you already talk** | Reach it by SMS, iMessage, email, or phone call. It replies quickly so you know it has started. |
| 🌙 **Stay awake** | Run all day on a small VM, restart itself after a reboot, and keep working when your laptop is closed. |

## Things you can ask

- "Check today's AI news. Pick one story and tell me why it matters."
- "Open the dashboard, download last month's report, and give me the key numbers."
- "Compare these options, check the latest prices, and send me the best three."
- "Turn the files in this folder into a short, clean brief."
- "Keep an eye on this task. If it fails, fix it and tell me when it is done."
- "Remember that I like short answers and morning flights."

## How it works

**You send a message → OpenInstinct does the work → You get the result**

OpenInstinct can run on your Mac or Linux computer. For an assistant that stays available when your laptop is closed, we recommend a small Ubuntu 24.04 VM.

## Set up your own

Choose where to run it:

- Your Mac or Linux computer
- **Recommended:** a small Ubuntu 24.04 VM that stays awake

You also need:

- A ChatGPT account with Codex access
- An [Inkbox](https://inkbox.ai) account for the phone number and messages

Open a terminal on your computer or VM and run one command:

```bash
curl -fsSL https://raw.githubusercontent.com/samagra14/openinstinct/main/install.sh | bash
```

Setup pauses twice so you can connect your ChatGPT account and create or choose your Inkbox identity. When it finishes, text `START` to the new number. Then send a normal request.

On a Mac or Linux computer, OpenInstinct stays available while that computer is awake.

## Good to know

- Routine work runs without asking you to approve every small step.
- It still asks before deleting important data, spending money, changing account security, or doing something hard to undo.
- Its working memory, files, browser logins, and conversation state live on your machine. Messages pass through Inkbox.
- Each allowed person gets a separate conversation, even when several people share the same assistant.

<details>
<summary><strong>Need to check or restart it?</strong></summary>

```bash
systemctl --user status openinstinct
systemctl --user restart openinstinct
journalctl --user -u openinstinct -f
```

You can also text `/status`, `/usage`, `/health`, `/stop`, `/new`, or `/resume`.

</details>

## Open source

OpenInstinct is a small open source setup that brings together Codex for the work and Inkbox for messaging. It is not affiliated with OpenAI, Inkbox, or Instinct.

[MIT License](LICENSE)
