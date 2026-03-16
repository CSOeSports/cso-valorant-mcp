<div align="center">
  <h1>🎯 Valorant MCP Server</h1>
  <p><strong>Model Context Protocol Server for Valorant Data</strong></p>
  
  [![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
  [![Python](https://img.shields.io/badge/Python-3.13+-ffd43b?logo=python&logoColor=blue)](https://www.python.org/)
  [![MCP](https://img.shields.io/badge/MCP-Ready-00E5FF)](https://modelcontextprotocol.io/)
  [![API](https://img.shields.io/badge/API-HenrikDev-red)](https://docs.henrikdev.xyz/)
</div>

<p align="center">
  A highly capable, community-driven Model Context Protocol (MCP) server that empowers your AI assistant to fetch real-time data from Valorant. Whether you're tracking performance, analyzing match history, or checking the competitive leaderboards, this MCP server seamlessly integrates Valorant statistics directly into your preferred AI clients.
</p>

---

## 📑 Table of Contents

- [Features](#-features)
- [Demo / Screenshots](#-demo--screenshots)
- [Tech Stack](#-tech-stack)
- [Getting Started](#-getting-started)
- [Usage / Setup](#-usage--setup)
- [Credits](#-credits)
- [License](#-license)

---

## ✨ Features

Equip your AI with comprehensive Valorant knowledge:

- 👤 **Account Lookups**: Retrieve account details, levels, and player cards using Riot ID or PUUID.
- 🏆 **Rank & MMR**: Check current competitive tier, Ranked Rating (RR), and full match rating history natively.
- 🔫 **Match History**: Access detailed summaries of recent games, filterable by map, mode, or platform.
- 📊 **Match Details**: Dive deep into post-game details, including economy, rounds, and per-player statistics.
- 🌐 **Leaderboards**: Pull ranked leaderboards for any region, filter for specific players, or check historical seasons.

---

## 📸 Demo / Screenshots

![demo](./assets/demo.gif)

> *(Visuals coming soon!)*

---

## 🛠 Tech Stack

Built with modern Python tooling for maximum performance and reliability:

- ![Python](https://img.shields.io/badge/Python-3.13-blue?logo=python&logoColor=white) **Python 3.13+**
- ![uv](https://img.shields.io/badge/uv-Package%20Manager-purple) **uv** for blazing-fast dependency management
- ![httpx](https://img.shields.io/badge/httpx-Async%20HTTP-green) **httpx** for non-blocking API calls
- ![MCP](https://img.shields.io/badge/MCP-Protocol-00E5FF) **mcp[cli]** for seamless Model Context Protocol integration

---

## 🚀 Getting Started

Follow these steps to get the server running locally on your machine.

### Prerequisites

- **Python 3.13** or higher installed.
- **uv** package manager installed (`pip install uv` or via standalone installer).
- A valid **Henrik API Key**. Get one at [HenrikDev Docs](https://docs.henrikdev.xyz/).

### Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/codeNilson/valorant-mcp-server
   cd valorant-mcp-server
   ```

2. **Sync dependencies using `uv`:**

   ```bash
   uv sync
   ```

3. **Configure Environment Variables:**
   Create a `.env` file in the root directory and add your API key:

   ```env
   HENRIK_API_KEY=your_api_key_here
   ```

---

## 🔌 Usage / Setup

To use this server, you need to configure your MCP client. Find your preferred client below and copy the configuration snippet.

> ⚠️ **Note:** Make sure to replace `C:\\path\\to\\valorant-mcp-server` with the actual absolute path to the directory where you cloned this repository.

### 🤖 Claude Desktop

**Where to find the config file:**

- **Windows:** `%APPDATA%\\Claude\\claude_desktop_config.json`
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Linux:** `~/.config/Claude/claude_desktop_config.json`

**Configuration:**

```json
{
  "mcpServers": {
    "valorant-mcp-server": {
      "command": "uv",
      "args": [
        "run",
        "valorant-mcp-server"
      ],
      "cwd": "C:\\path\\to\\valorant-mcp-server",
      "env": {
        "HENRIK_API_KEY": "your_api_key_here"
      }
    }
  }
}
```

*Restart Claude Desktop entirely after saving the file.*

### 🌌 Antigravity

**Where to find the config file:**

- Built into the Antigravity UI directly, usually in Settings -> MCP Servers.

**Configuration:**
Simply add this to your MCP servers configuration menu or JSON:

```json
{
  "mcpServers": {
    "valorant": {
      "command": "uv",
      "args": [
        "run",
        "valorant-mcp-server"
      ],
      "cwd": "C:\\path\\to\\valorant-mcp-server",
      "env": {
        "HENRIK_API_KEY": "your_api_key_here"
      }
    }
  }
}
```

*No restart usually required, but refresh if necessary.*

### 💻 VS Code (Roo Code / Cline)

**Where to find the config file:**

- Typically located in `~/.vscode/mcp.json` or within the extension's specific MCP settings UI. (e.g., `%APPDATA%\\Code\\User\\globalStorage\\rooveterinaryinc.roo-cline\\settings\\cline_mcp_settings.json` on Windows).

**Configuration:**

```json
{
  "mcpServers": {
    "valorant": {
      "command": "uv",
      "args": [
        "run",
        "valorant-mcp-server"
      ],
      "cwd": "C:\\path\\to\\valorant-mcp-server",
      "env": {
        "HENRIK_API_KEY": "your_api_key_here"
      }
    }
  }
}
```

*Reload the VS Code window (`Ctrl+Shift+P` -> `Developer: Reload Window`) after saving.*

---

## 🙏 Credits

This project is made possible thanks to the **Henrik API** providing the unofficial Valorant API data endpoints.

- ⚡ **API Documentation**: [https://docs.henrikdev.xyz](https://docs.henrikdev.xyz)
- ⚠️ **Disclaimer**: This project is an unofficial community creation and is **not** affiliated with, endorsed, or sponsored by Riot Games or Valorant. Valorant and Riot Games are trademarks or registered trademarks of Riot Games, Inc.

---

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
