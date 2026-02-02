<p align="center">
  <img src="https://img.shields.io/badge/MCP-Compatible-blueviolet?style=for-the-badge" alt="MCP Compatible"/>
  <img src="https://img.shields.io/badge/Gemini-2.0_Flash-4285F4?style=for-the-badge&logo=google&logoColor=white" alt="Gemini 2.0"/>
  <img src="https://img.shields.io/badge/LangGraph-Agentic-FF6B6B?style=for-the-badge" alt="LangGraph"/>
  <img src="https://img.shields.io/badge/Notion-Integration-000000?style=for-the-badge&logo=notion&logoColor=white" alt="Notion"/>
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="MIT License"/>
</p>

<h1 align="center">🧠 Notion Research Buddy</h1>

<p align="center">
  <strong>Transform messy research notes into polished documentation with AI-powered refinement and auto-generated architecture diagrams.</strong>
</p>

<p align="center">
  A stateful agentic workflow that connects <b>Notion</b> • <b>LangGraph</b> • <b>Gemini 2.0</b> via the <b>Model Context Protocol (MCP)</b>
</p>

---

## ✨ Features

| Feature                           | Description                                                              |
| --------------------------------- | ------------------------------------------------------------------------ |
| 🧹 **Smart Note Refinement**      | Cleans up raw, chaotic notes into beautifully structured Markdown        |
| 📊 **Auto Architecture Diagrams** | Generates Mermaid.js diagrams automatically from your content            |
| 🔌 **MCP Native**                 | Works seamlessly with Claude Desktop, Antigravity, and other MCP clients |
| 📝 **Notion Sync**                | Reads from and writes results directly back to your Notion pages         |
| 🌐 **Dual Mode**                  | Run as MCP server OR standalone HTTP API server                          |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                       MCP CLIENT                                │
│              (Claude Desktop / Antigravity)                     │
└─────────────────────┬───────────────────────────────────────────┘
                      │ MCP Protocol (stdio)
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                    RESEARCH BUDDY SERVER                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                   LangGraph Workflow                      │  │
│  │  ┌─────────────┐         ┌──────────────────────────┐    │  │
│  │  │   Refiner   │────────▶│      Architect          │    │  │
│  │  │    Node     │         │        Node             │    │  │
│  │  │  (Clean up) │         │  (Diagram Generation)   │    │  │
│  │  └─────────────┘         └──────────────────────────┘    │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                  │
│                    Gemini 2.0 Flash                             │
│              (via OpenAI-compatible adapter)                    │
└─────────────────────┬───────────────────────────────────────────┘
                      │ Notion API
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                      NOTION WORKSPACE                           │
│                   (Your Research Pages)                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Notion Integration Token ([Create one here](https://www.notion.so/my-integrations))
- Google Gemini API Key ([Get one here](https://aistudio.google.com/apikey))

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/notion-research-buddy.git
cd notion-research-buddy

# Create virtual environment
python -m venv .venv

#  Activate it
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

# Install dependencies
pip install -r requirements.txt
```

### Configuration

1. **Copy the example environment file:**

   ```bash
   copy .env.example .env    # Windows
   # cp .env.example .env    # macOS/Linux
   ```

2. **Edit `.env` with your API keys:**

   ```env
   NOTION_API_KEY=secret_xxxxxxxxxxxxx
   GEMINI_API_KEY=AIzaSyxxxxxxxxxxxxxxxxx
   LANGCHAIN_API_KEY=lsv2_pt_xxxxx  # Optional: for LangSmith tracing
   ```

3. **Share your Notion page** with your integration (in Notion, click "..." → "Connections" → add your integration)

---

## 🔧 Running the Server

### Option 1: MCP Server Mode (Default)

```bash
python server.py
```

Connect via Claude Desktop, Antigravity, or any MCP-compatible client.

### Option 2: HTTP API Mode

```bash
python server.py --http
```

API available at `http://localhost:8000` with interactive docs at `/docs`.

---

## 🔌 MCP Configuration

### For Antigravity

Add to `~/.gemini/antigravity/mcp_config.json`:

```json
{
  "mcpServers": {
    "notion-research-buddy": {
      "command": "C:/path/to/notion-mcp-agent/.venv/Scripts/python.exe",
      "args": ["C:/path/to/notion-mcp-agent/server.py"],
      "env": {
        "NOTION_API_KEY": "secret_xxxxxxxxxxxxx",
        "GEMINI_API_KEY": "AIzaSyxxxxxxxxxxxxxxxxx"
      }
    }
  }
}
```

### For Claude Desktop

Add to your Claude Desktop MCP configuration with similar settings.

> **⚠️ Important:** Restart your MCP client after modifying the configuration.

---

## 🛠️ Available Tools

| Tool                            | Description                                                                    |
| ------------------------------- | ------------------------------------------------------------------------------ |
| `process_research_page`         | 🔄 Full pipeline: reads page → refines notes → generates diagram → writes back |
| `get_page_content`              | 📖 Read-only: extracts and returns raw text from a Notion page                 |
| `combine_architecture_diagrams` | 🔗 Merges multiple Mermaid diagrams into a unified system architecture         |

---

## 💡 Usage Examples

### Via MCP Client

> _"Process the research notes on page 25c0b47f1a28803fae5ece3c6125e7ea"_

The assistant will:

1. Read your messy notes from Notion
2. Refine them into clean, structured Markdown
3. Generate a Mermaid architecture diagram
4. Write everything back to your page

### Via HTTP API

```bash
# Get page content
curl http://localhost:8000/content/YOUR_PAGE_ID

# Process page (refine + diagram)
curl -X POST http://localhost:8000/process/YOUR_PAGE_ID

# Combine multiple diagrams into one
curl -X POST http://localhost:8000/combine-diagrams \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Unified Architecture",
    "diagrams": [
      {"label": "System A", "mermaid_code": "graph TD\n  A-->B"},
      {"label": "System B", "mermaid_code": "graph TD\n  C-->D"}
    ]
  }'
```

---

## 📁 Project Structure

```
notion-mcp-agent/
├── server.py          # Main server (MCP + HTTP modes)
├── requirements.txt   # Python dependencies
├── .env.example       # Example environment config
├── .env               # Your API keys (gitignored)
└── README.md          # You are here!
```

---

## 🔍 How It Works

The **LangGraph workflow** consists of two AI-powered nodes:

1. **🧹 Refiner Node**
   - Takes raw, unstructured notes
   - Uses Gemini 2.0 Flash to clean and structure them
   - Outputs well-organized Markdown with headers, bullets, and emphasis

2. **📊 Architect Node**
   - Analyzes the refined content
   - Generates a Mermaid.js diagram representing the system architecture or flow
   - Supports `graph TD`, `sequenceDiagram`, and other Mermaid types

---

## 📜 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

---

<p align="center">
  <strong>Built with 💜 by the community</strong>
</p>

<p align="center">
  <sub>Powered by Notion API • LangGraph • Gemini 2.0 Flash • FastMCP</sub>
</p>
