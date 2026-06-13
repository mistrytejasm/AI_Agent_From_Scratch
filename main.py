import asyncio
import json
from datetime import datetime, timezone
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, IntPrompt
from rich.text import Text
from rich.live import Live

from database.connection import db_client
from config.settings import settings
from memory.mongo_history import MongoDBChatHistory
from memory.short_term import ShortTermMemory
from llm.groq_provider import GroqProvider
from agent.simple_agent import SimpleAgent

# Crucial: Import the tools package to load all decorators and register functions
import tools

console = Console()

async def get_or_create_session(db_history: MongoDBChatHistory) -> str:
    """Prompts the user to select an existing chat session or start a new one."""
    console.print(Panel("[bold cyan]Session Manager[/bold cyan]\n1. Start a New Conversation\n2. Load an Existing Conversation"))
    choice = IntPrompt.ask("Choose an option", choices=["1", "2"], default=1)
    
    if choice == 2:
        sessions = await db_history.get_all_sessions()
        if not sessions:
            console.print("[yellow]No existing sessions found. Starting a new session...[/yellow]")
            return await db_history.create_session()
        
        console.print("\n[bold green]Available Chat Sessions:[/bold green]")
        for idx, s in enumerate(sessions, 1):
            updated_str = s.get("updated_at", datetime.now(timezone.utc)).strftime("%Y-%m-%d %H:%M:%S")
            console.print(f"{idx}. {s['title']} [dim](<Last active: {updated_str}>)[/dim] - ID: {s['_id']}")
            
        choices = [str(i) for i in range(1, len(sessions) + 1)]
        selected_idx = IntPrompt.ask("\nSelect session number", choices=choices)
        selected_session = sessions[selected_idx - 1]
        console.print(f"[green]Loaded session: [bold]{selected_session['title']}[/bold][/green]\n")
        return selected_session["_id"]
    
    title = Prompt.ask("Enter conversation title", default="New Conversation")
    session_id = await db_history.create_session(title)
    console.print(f"[green]Created new session: [bold]{title}[/bold] (ID: {session_id})[/green]\n")
    return session_id

async def run_cli():
    # Open database connection pool
    db_client.connect()
    
    console.print(Panel(
        "[bold magenta]Scalable Python AI Agent[/bold magenta]\n"
        "Equipped with 6 tools: Calculator, Tavily Search, File IO, System Clock.",
        title="Welcome",
        subtitle="v2.0.0"
    ))
    
    # Initialize components
    db_history = MongoDBChatHistory()
    short_memory = ShortTermMemory(storage=db_history, max_messages=settings.max_messages)
    groq_llm = GroqProvider()
    agent = SimpleAgent(llm=groq_llm, memory=short_memory)
    
    # Load or create conversation session
    session_id = await get_or_create_session(db_history)
    
    # Help Commands
    console.print("[dim]Commands: type [/dim][bold red]/exit[/bold red][dim] to quit, [/dim][bold yellow]/clear[/bold yellow][dim] to clear history for this session.[/dim]\n")
    
    # Print history if loading an existing session
    past_messages = await db_history.get_messages(session_id)
    if past_messages:
        console.print("[bold dim]--- Loaded History ---[/bold dim]")
        for msg in past_messages:
            # Skip displaying internal tool calls/results in CLI history
            if msg["role"] == "tool" or msg.get("tool_calls"):
                continue
            role_color = "bold cyan" if msg["role"] == "user" else "bold green"
            console.print(f"[{role_color}]{msg['role'].capitalize()}:[/{role_color}] {msg['content']}")
        console.print("[bold dim]------------------------[/bold dim]\n")
        
    while True:
        try:
            user_input = Prompt.ask("[bold cyan]You[/bold cyan]")
            
            if not user_input.strip():
                continue
                
            if user_input.lower() == "/exit":
                console.print("[yellow]Exiting chatbot... Goodbye![/yellow]")
                break
                
            if user_input.lower() == "/clear":
                await short_memory.clear(session_id)
                console.print("[red]Cleared history for this session.[/red]\n")
                continue
                
            console.print("[bold green]Assistant:[/bold green]")
            
            response_text = ""
            live = None
            
            async for token in agent.run_stream(session_id, user_input):
                if token.startswith("__TOOL_CALL__"):
                    # If we have an active typewriter text stream open, stop it
                    if live:
                        live.stop()
                        live = None
                    
                    # Parse the tool name and JSON string arguments
                    _, tool_name, args_str = token.split(":", 2)
                    try:
                        args = json.loads(args_str)
                        args_fmt = ", ".join(f"{k}={json.dumps(v)}" for k, v in args.items())
                    except Exception:
                        args_fmt = args_str
                        
                    console.print(f"  [bold yellow]🔧 Running tool: [cyan]{tool_name}({args_fmt})[/cyan]...[/bold yellow]")
                else:
                    # Standard text response - open a typewriter stream if not active
                    if not live:
                        response_text = ""
                        live = Live(Text(""), refresh_per_second=15, console=console)
                        live.start()
                        
                    response_text += token
                    live.update(Text(response_text))
            
            if live:
                live.stop()
            console.print()  # Add final blank line
            
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted by user. Exiting...[/yellow]")
            break
        except Exception as e:
            console.print(f"\n[bold red]Error occurred:[/bold red] {e}")
            
    # Close database connection pool safely on exit
    db_client.disconnect()

def main():
    asyncio.run(run_cli())

if __name__ == "__main__":
    main()