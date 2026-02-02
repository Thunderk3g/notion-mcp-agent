"""
Notion Research Buddy - MCP Server + HTTP API
==============================================
A stateful refinement agent that connects Notion, LangGraph, and Gemini.

Usage:
    python server.py          # Run as MCP server (default)
    python server.py --http   # Run as HTTP API server on port 8000
"""

import os
import sys
import logging
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from fastmcp import FastMCP
from pydantic import BaseModel, Field
from notion_client import Client
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END

# Load environment variables
load_dotenv()

# --- 1. Configuration & Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("research-buddy")

NOTION_API_KEY = os.environ.get("NOTION_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not NOTION_API_KEY:
    logger.warning("NOTION_API_KEY not set. Notion operations will fail.")
if not GEMINI_API_KEY:
    logger.warning("GEMINI_API_KEY not set. LLM operations will fail.")

notion = Client(auth=NOTION_API_KEY)
mcp = FastMCP("Notion Research Buddy")

# --- 2. Data Models (Strict Mode) ---
class AgentState(BaseModel):
    """The shared memory of the agent as it thinks."""
    raw_notes: str = Field(..., description="Raw text from Notion")
    refined_notes: Optional[str] = Field(None, description="Cleaned markdown")
    mermaid_code: Optional[str] = Field(None, description="Mermaid diagram code")
    page_id: str


class PageContext(BaseModel):
    """Input model for MCP tools."""
    page_id: str = Field(..., description="Notion Page ID (32 characters, no dashes)")


class DiagramInput(BaseModel):
    """A single diagram with its source label."""
    label: str = Field(..., description="Label for this diagram (e.g., 'PersonaPlex', 'MemoRAG')")
    mermaid_code: str = Field(..., description="Raw Mermaid diagram code")


class CombineDiagramsContext(BaseModel):
    """Input model for combining multiple diagrams."""
    diagrams: list[DiagramInput] = Field(..., description="List of diagrams to combine")
    title: str = Field(default="Unified Architecture", description="Title for the combined diagram")


# --- 3. The Brain (LangGraph) ---
# We use Gemini 2.0 Flash via the OpenAI Adapter for LangChain compatibility
llm = ChatOpenAI(
    api_key=GEMINI_API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    model="gemini-2.0-flash",
    temperature=0.2
)


def rewrite_notes_node(state: AgentState) -> Dict[str, Any]:
    """Node 1: Refine raw notes into clean markdown."""
    logger.info("🧠 Refiner: Cleaning notes...")
    prompt = f"""
    Refine these raw notes into clean, structured Markdown.
    Use headers, bullets, and bold text. Keep all information.
    
    Raw Notes:
    {state.raw_notes}
    """
    response = llm.invoke(prompt)
    return {"refined_notes": response.content}


def generate_diagram_node(state: AgentState) -> Dict[str, Any]:
    """Node 2: Generate a Mermaid diagram from the content."""
    logger.info("🏗️ Architect: Generating diagram...")
    content = state.refined_notes or state.raw_notes
    prompt = f"""
    Analyze this text and generate a Mermaid.js diagram (graph TD or sequenceDiagram)
    that represents the system architecture or flow.
    Return ONLY the Mermaid code, no markdown code blocks.
    
    Text:
    {content}
    """
    response = llm.invoke(prompt)
    # Clean up markdown code blocks if present
    code = response.content.replace("```mermaid", "").replace("```", "").strip()
    return {"mermaid_code": code}


# Define the Workflow
workflow = StateGraph(AgentState)
workflow.add_node("refiner", rewrite_notes_node)
workflow.add_node("architect", generate_diagram_node)
workflow.set_entry_point("refiner")
workflow.add_edge("refiner", "architect")
workflow.add_edge("architect", END)
app = workflow.compile()


# --- 4. The MCP Tools ---

@mcp.tool()
def process_research_page(ctx: PageContext) -> str:
    """
    Main Entrypoint: Reads a Notion page, runs the AI agent to refine notes
    and generate a diagram, then updates the page with the results.
    
    Args:
        ctx: PageContext containing the Notion page_id
        
    Returns:
        Success or error message
    """
    page_id = ctx.page_id
    logger.info(f"📖 Processing Page: {page_id}")

    # A. Read Notion
    try:
        blocks = notion.blocks.children.list(block_id=page_id)
        # Extract text from paragraph blocks
        raw_text_parts = []
        for block in blocks["results"]:
            if block["type"] == "paragraph" and block["paragraph"]["rich_text"]:
                for text_item in block["paragraph"]["rich_text"]:
                    raw_text_parts.append(text_item["plain_text"])
        raw_text = "\n".join(raw_text_parts)
    except Exception as e:
        logger.error(f"Error reading Notion: {e}")
        return f"Error reading Notion: {e}"

    if not raw_text.strip():
        return "⚠️ Page is empty or contains no paragraph text."

    logger.info(f"📝 Extracted {len(raw_text)} characters from page")

    # B. Run Agent
    try:
        state = AgentState(raw_notes=raw_text, page_id=page_id)
        result = app.invoke(state)
    except Exception as e:
        logger.error(f"Error running agent: {e}")
        return f"Error running agent: {e}"

    # C. Write Back to Notion
    try:
        # Add a divider first
        notion.blocks.children.append(page_id, children=[{
            "object": "block",
            "type": "divider",
            "divider": {}
        }])
        
        # Add heading for refined notes
        notion.blocks.children.append(page_id, children=[{
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": "✨ Refined Notes"}}]
            }
        }])
        
        # Append refined text (truncate if too long for Notion's limit)
        refined_content = result["refined_notes"][:2000] if result.get("refined_notes") else ""
        if refined_content:
            notion.blocks.children.append(page_id, children=[{
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": refined_content}}]
                }
            }])

        # Add heading for diagram
        notion.blocks.children.append(page_id, children=[{
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": "📊 Architecture Diagram"}}]
            }
        }])
        
        # Append Mermaid Diagram as a code block
        mermaid_code = result.get("mermaid_code", "")
        if mermaid_code:
            notion.blocks.children.append(page_id, children=[{
                "object": "block",
                "type": "code",
                "code": {
                    "rich_text": [{"type": "text", "text": {"content": mermaid_code}}],
                    "language": "mermaid"
                }
            }])
        
        logger.info("✅ Successfully updated Notion page!")
        return "✅ Page refined and diagram added!"
        
    except Exception as e:
        logger.error(f"Error writing to Notion: {e}")
        return f"Error writing to Notion: {e}"


@mcp.tool()
def get_page_content(ctx: PageContext) -> str:
    """
    Read and return the raw text content of a Notion page.
    Useful for inspecting what's on a page before processing.
    
    Args:
        ctx: PageContext containing the Notion page_id
        
    Returns:
        The extracted text content or an error message
    """
    page_id = ctx.page_id
    logger.info(f"📖 Reading Page: {page_id}")
    
    try:
        blocks = notion.blocks.children.list(block_id=page_id)
        raw_text_parts = []
        for block in blocks["results"]:
            block_type = block["type"]
            if block_type == "paragraph" and block[block_type]["rich_text"]:
                for text_item in block[block_type]["rich_text"]:
                    raw_text_parts.append(text_item["plain_text"])
            elif block_type in ["heading_1", "heading_2", "heading_3"]:
                if block[block_type]["rich_text"]:
                    header_text = "".join([t["plain_text"] for t in block[block_type]["rich_text"]])
                    raw_text_parts.append(f"\n{'#' * int(block_type[-1])} {header_text}\n")
            elif block_type == "bulleted_list_item" and block[block_type]["rich_text"]:
                for text_item in block[block_type]["rich_text"]:
                    raw_text_parts.append(f"• {text_item['plain_text']}")
                    
        return "\n".join(raw_text_parts) if raw_text_parts else "⚠️ Page is empty."
    except Exception as e:
        logger.error(f"Error reading Notion: {e}")
        return f"Error reading Notion: {e}"


@mcp.tool()
def combine_architecture_diagrams(ctx: CombineDiagramsContext) -> str:
    """
    Combine multiple Mermaid architecture diagrams into a single unified diagram.
    Uses AI to intelligently merge diagrams, identifying relationships between components.
    
    Args:
        ctx: CombineDiagramsContext containing list of diagrams and optional title
        
    Returns:
        Combined Mermaid diagram code
    """
    logger.info(f"🔗 Combining {len(ctx.diagrams)} diagrams...")
    
    if not ctx.diagrams:
        return "⚠️ No diagrams provided to combine."
    
    if len(ctx.diagrams) == 1:
        return ctx.diagrams[0].mermaid_code
    
    # Build the prompt with all diagrams
    diagrams_text = "\n\n".join([
        f"### {d.label}\n```mermaid\n{d.mermaid_code}\n```"
        for d in ctx.diagrams
    ])
    
    prompt = f"""
    You are an expert at creating Mermaid.js architecture diagrams.
    
    I have {len(ctx.diagrams)} separate architecture diagrams that I need you to combine 
    into ONE unified system architecture diagram titled "{ctx.title}".
    
    Requirements:
    1. Create a single cohesive graph TD diagram
    2. Group each original diagram as a named subgraph
    3. Identify logical connections BETWEEN the different systems
    4. Use consistent styling and clear node names
    5. Add a main title subgraph wrapping everything
    6. Keep node labels concise but descriptive
    7. Return ONLY the Mermaid code, no markdown blocks or explanations
    
    Here are the diagrams to combine:
    
    {diagrams_text}
    
    Generate the combined Mermaid diagram:
    """
    
    try:
        response = llm.invoke(prompt)
        # Clean up any markdown code blocks if present
        code = response.content.replace("```mermaid", "").replace("```", "").strip()
        logger.info("✅ Successfully combined diagrams!")
        return code
    except Exception as e:
        logger.error(f"Error combining diagrams: {e}")
        return f"Error combining diagrams: {e}"


# --- 5. HTTP API Server (Alternative to MCP) ---
def create_http_app():
    """Create a FastAPI app for direct HTTP access."""
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    
    http_app = FastAPI(
        title="Notion Research Buddy API",
        description="Direct HTTP API for processing Notion pages",
        version="1.0.0"
    )
    
    http_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    @http_app.get("/")
    def root():
        return {"status": "ok", "message": "Notion Research Buddy API is running!"}
    
    @http_app.get("/content/{page_id}")
    def get_content(page_id: str):
        """Get raw content from a Notion page."""
        ctx = PageContext(page_id=page_id)
        result = get_page_content(ctx)
        if result.startswith("Error"):
            raise HTTPException(status_code=400, detail=result)
        return {"page_id": page_id, "content": result}
    
    @http_app.post("/process/{page_id}")
    def process_page(page_id: str):
        """Process a Notion page: refine notes and generate diagram."""
        ctx = PageContext(page_id=page_id)
        result = process_research_page(ctx)
        if result.startswith("Error"):
            raise HTTPException(status_code=400, detail=result)
        return {"page_id": page_id, "result": result}
    
    @http_app.post("/combine-diagrams")
    def combine_diagrams(request: CombineDiagramsContext):
        """Combine multiple Mermaid diagrams into a unified architecture diagram."""
        result = combine_architecture_diagrams(request)
        if result.startswith("Error"):
            raise HTTPException(status_code=400, detail=result)
        return {"title": request.title, "combined_diagram": result}
    
    return http_app


if __name__ == "__main__":
    if "--http" in sys.argv:
        # Run as HTTP API server
        import uvicorn
        logger.info("🌐 Starting HTTP API Server on http://localhost:8000")
        logger.info("📖 Docs available at http://localhost:8000/docs")
        http_app = create_http_app()
        uvicorn.run(http_app, host="0.0.0.0", port=8000)
    else:
        # Run as MCP server (default)
        logger.info("🚀 Starting Notion Research Buddy MCP Server...")
        mcp.run()
