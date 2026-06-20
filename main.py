import asyncio
import json
from datetime import datetime, timezone
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, IntPrompt
from rich.text import Text
from rich.live import Live
from rich.table import Table

from database.connection import db_client
from config.settings import settings
from memory.mongo_history import MongoDBChatHistory
from memory.short_term import ShortTermMemory
from llm.groq_provider import GroqProvider
from agent.simple_agent import SimpleAgent
from memory.consolidator import MemoryConsolidator

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

async def display_sessions_table(db_history: MongoDBChatHistory, current_session_id: str):
    """Fetches all saved chat sessions and prints them in a formatted Rich Table."""
    sessions = await db_history.get_all_sessions()
    if not sessions:
        console.print("[yellow]No saved chat sessions found.[/yellow]\n")
        return
    
    table = Table(title="[bold cyan]Saved Chat Sessions[/bold cyan]")
    table.add_column("#", justify="right", style="dim")
    table.add_column("Title", style="green")
    table.add_column("Last Active", style="magenta")
    table.add_column("Session ID", style="dim")
    table.add_column("Status", style="yellow")
    
    for idx, s in enumerate(sessions, 1):
        s_id = s["_id"]
        updated_str = s.get("updated_at", datetime.now(timezone.utc)).strftime("%Y-%m-%d %H:%M:%S")
        status = "[bold yellow]* Active[/bold yellow]" if s_id == current_session_id else ""
        table.add_row(str(idx), s["title"], updated_str, s_id, status)
        
    console.print(table)
    console.print()

async def run_cli():
    # Open database connection pool
    db_client.connect()
    
    console.print(Panel(
        "[bold magenta]Scalable Python AI Agent[/bold magenta]\n"
        "Equipped with Long-Term Memory, Vector Search, and local Embeddings.",
        title="Welcome",
        subtitle="v2.2.0"
    ))
    
    # Initialize components
    db_history = MongoDBChatHistory()
    short_memory = ShortTermMemory(storage=db_history, max_messages=settings.max_messages)
    groq_llm = GroqProvider()
    
    if settings.use_local_llm:
        from llm.local_openai import LocalOpenAIProvider
        from llm.fallback_provider import FallbackLLMProvider
        local_llm = LocalOpenAIProvider()
        llm = FallbackLLMProvider(primary=local_llm, fallback=groq_llm)
    else:
        llm = groq_llm
        
    agent = SimpleAgent(llm=llm, memory=short_memory)
    consolidator = MemoryConsolidator(llm_provider=llm)
    
    # Pre-load local embedding model weights at startup
    with console.status("[bold green]Loading local embedding model...[/bold green]", spinner="dots"):
        await agent.long_term_memory.embedding_client.initialize()
    
    # Outer loop for session lifecycle (allows returning to Session Manager without exiting)
    while True:
        # Load or create conversation session
        session_id = await get_or_create_session(db_history)
        
        # Help Commands Console Info
        console.print(
            "[bold yellow]Available Commands:[/bold yellow]\n"
            "  [bold red]/exit[/bold red] [dim]................. Exit chat & save session summary[/dim]\n"
            "  [bold yellow]/clear[/bold yellow] [dim]................ Clear chat history for the active session[/dim]\n"
            "  [bold cyan]/memories[/bold cyan] [dim]............. List all stored active long-term memories[/dim]\n"
            "  [bold magenta]/forget [topic][/bold magenta] [dim]......... Delete memories matching a topic (or --all)[/dim]\n"
            "  [bold blue]/consolidate[/bold blue] [dim]........... Manually trigger memory consolidation/cleanup[/dim]\n"
            "  [bold green]/sessions[/bold green] [dim].............. List all saved chat sessions in database[/dim]\n"
            "  [bold red]/forget_session [num/ID][/bold red] [dim]Delete a session and its messages (or --all)[/dim]\n"
        )
        
        # Print history if loading an existing session
        past_messages = await db_history.get_messages(session_id)
        if past_messages:
            console.print("[bold dim]--- Loaded History ---[/bold dim]")
            for msg in past_messages:
                if msg["role"] == "tool" or msg.get("tool_calls"):
                    continue
                role_color = "bold cyan" if msg["role"] == "user" else "bold green"
                console.print(f"[{role_color}]{msg['role'].capitalize()}:[/{role_color}] {msg['content']}")
            console.print("[bold dim]------------------------[/bold dim]\n")
            
        should_exit_program = False
        
        while True:
            try:
                user_input = Prompt.ask("[bold cyan]You[/bold cyan]")
                
                if not user_input.strip():
                    continue
                    
                # 1. Exit & Summarize command
                if user_input.lower() == "/exit":
                    console.print("[green][dim]Saving session summary...[/dim]")
                    summary = await agent.save_session_summary(session_id)
                    if summary:
                        console.print(f"[green]✓ Saved session summary:[/green] [dim]\"{summary}\"[/dim]")
                    console.print("[yellow]Exiting chatbot... Goodbye![/yellow]")
                    should_exit_program = True
                    break
                    
                # 2. Clear session history command
                if user_input.lower() == "/clear":
                    await short_memory.clear(session_id)
                    console.print("[red]Cleared history for this session.[/red]\n")
                    continue

                # 3. View memories command
                if user_input.lower() == "/memories":
                    memories = await agent.long_term_memory.list_all("default_user")
                    if not memories:
                        console.print("[yellow]No stored long-term memories found.[/yellow]\n")
                        continue
                    
                    table = Table(title="[bold cyan]Stored Long-Term Memories[/bold cyan]")
                    table.add_column("#", justify="right", style="dim")
                    table.add_column("Fact", style="green")
                    table.add_column("Category", style="magenta")
                    table.add_column("Confidence", justify="right", style="cyan")
                    table.add_column("Accesses", justify="right", style="yellow")
                    table.add_column("Memory ID", style="dim")
                    
                    for idx, m in enumerate(memories, 1):
                        conf = f"{m.get('confidence', 1.0):.2f}"
                        accesses = str(m.get("access_count", 0))
                        m_id = str(m["_id"])
                        table.add_row(str(idx), m["fact"], m["category"], conf, accesses, m_id)
                        
                    console.print(table)
                    console.print()
                    continue

                # 4. Forget memory command (handles specific topics or --all)
                if user_input.lower().startswith("/forget") and not user_input.lower().startswith("/forget_session"):
                    parts = user_input.split(maxsplit=1)
                    if len(parts) < 2:
                        console.print("[red]Usage: /forget [topic] or /forget --all[/red]\n")
                        continue
                    
                    topic = parts[1].strip()
                    if topic == "--all":
                        confirm = Prompt.ask(
                            "[bold red]Are you sure you want to delete ALL long-term memories? (yes/no)[/bold red]",
                            choices=["yes", "no"],
                            default="no"
                        )
                        if confirm == "yes":
                            deleted_count = await agent.long_term_memory.delete_by_topic("default_user", "--all")
                            console.print(f"[red]Deleted all {deleted_count} memories for this user.[/red]\n")
                        else:
                            console.print("[yellow]Cancelled deletion.[/yellow]\n")
                    else:
                        deleted_count = await agent.long_term_memory.delete_by_topic("default_user", topic)
                        if deleted_count > 0:
                            console.print(f"[green]Successfully forgot {deleted_count} memories matching '[bold]{topic}[/bold]'.[/green]\n")
                        else:
                            console.print(f"[yellow]No memories found matching '[bold]{topic}[/bold]'.[/yellow]\n")
                    continue

                # 5. Consolidate database command
                if user_input.lower() == "/consolidate":
                    console.print("[bold yellow]Running memory consolidation pipeline...[/bold yellow]")
                    report = await consolidator.consolidate("default_user")
                    
                    report_text = (
                        f"🟢 [bold green]Stale Deleted:[/bold green] {report['stale_deleted']}\n"
                        f"    (0 access counts and older than 30 days)\n\n"
                        f"🟡 [bold yellow]Duplicates Merged:[/bold yellow] {report['duplicates_merged']}\n"
                        f"    (Identified exact duplicates with >0.95 similarity)\n\n"
                        f"🔴 [bold red]Conflicts Resolved:[/bold red] {report['conflicts_resolved']}\n"
                        f"    (Contradictions detected with 0.85-0.95 similarity)\n\n"
                        f"🔵 [bold blue]Categories Summarized:[/bold blue] {report['categories_summarized']}\n"
                        f"    (Bloated categories compressed into clean facts)"
                    )
                    console.print(Panel(report_text, title="Memory Consolidation Report"))
                    console.print()
                    continue

                # 6. List all saved chat sessions in database command
                if user_input.lower() == "/sessions":
                    await display_sessions_table(db_history, session_id)
                    continue

                # 7. Forget chat session command (number or raw ID) or --all
                if user_input.lower().startswith("/forget_session"):
                    parts = user_input.split(maxsplit=1)
                    if len(parts) < 2:
                        console.print("[red]Usage: /forget_session [number/ID] or /forget_session --all[/red]\n")
                        continue
                    
                    target = parts[1].strip()
                    if target == "--all":
                        confirm = Prompt.ask(
                            "[bold red]Are you sure you want to delete ALL chat sessions and message history? This will return you to the Session Manager. (yes/no)[/bold red]",
                            choices=["yes", "no"],
                            default="no"
                        )
                        if confirm == "yes":
                            deleted_count = await db_history.delete_all_sessions()
                            console.print(f"[red]Deleted all {deleted_count} chat sessions and all message history.[/red]\n")
                            console.print("[yellow]All sessions deleted. Returning to Session Manager...[/yellow]\n")
                            await agent.cleanup()
                            break
                        else:
                            console.print("[yellow]Cancelled deletion.[/yellow]\n")
                    else:
                        sessions = await db_history.get_all_sessions()
                        target_id = None
                        target_title = ""

                        # Parse selected session index number
                        try:
                            idx = int(target)
                            if 1 <= idx <= len(sessions):
                                target_id = sessions[idx - 1]["_id"]
                                target_title = sessions[idx - 1]["title"]
                        except ValueError:
                            # Fallback: Parse as raw ObjectId hex string
                            target_id = target
                            for s in sessions:
                                if s["_id"] == target_id:
                                    target_title = s["title"]
                                    break

                        if not target_id:
                            console.print(f"[red]Invalid session selection: '{target}'[/red]\n")
                            continue

                        # Explicit warning if deleting the currently active session
                        if target_id == session_id:
                            confirm = Prompt.ask(
                                f"[bold red]WARNING: '{target_title}' is the CURRENT active session. "
                                f"Deleting it will delete the history and return you to the Session Manager. Proceed? (yes/no)[/bold red]",
                                choices=["yes", "no"],
                                default="no"
                            )
                        else:
                            confirm = Prompt.ask(
                                f"Are you sure you want to delete session '{target_title}'? (yes/no)",
                                choices=["yes", "no"],
                                default="no"
                            )

                        if confirm == "yes":
                            await db_history.delete_session(target_id)
                            console.print(f"[red]Deleted session '{target_title}' and its messages.[/red]\n")
                            
                            # Return to Session Manager if the currently running active session is deleted
                            if target_id == session_id:
                                console.print("[yellow]The active session was deleted. Returning to Session Manager...[/yellow]\n")
                                await agent.cleanup()
                                break
                            
                            # Automatically print the updated list so the user sees the new indices
                            await display_sessions_table(db_history, session_id)
                        else:
                            console.print("[yellow]Cancelled deletion.[/yellow]\n")
                    continue
                    
                console.print("[bold green]Assistant:[/bold green]")
                
                response_text = ""
                live = None
                
                async for token in agent.run_stream(session_id, user_input):
                    if token.startswith("__TOOL_CALL__"):
                        if live:
                            live.stop; live = None
                        
                        _, tool_name, args_str = token.split(":", 2)
                        try:
                            args = json.loads(args_str)
                            args_fmt = ", ".join(f"{k}={json.dumps(v)}" for k, v in args.items())
                        except Exception:
                            args_fmt = args_str
                            
                        console.print(f"  [bold yellow]🔧 Running tool: [cyan]{tool_name}({args_fmt})[/cyan]...[/bold yellow]")
                    else:
                        if not live:
                            response_text = ""
                            live = Live(Text(""), refresh_per_second=15, console=console)
                            live.start()
                            
                        response_text += token
                        live.update(Text(response_text))
                
                if live:
                    live.stop()
                console.print()
                
            except KeyboardInterrupt:
                console.print("\n[yellow]Interrupted by user. Exiting...[/yellow]")
                should_exit_program = True
                break
            except Exception as e:
                console.print(f"\n[bold red]Error occurred:[/bold red] {e}")
                
        if should_exit_program:
            break
            
    # Close database connection pool safely on exit
    db_client.disconnect()

def main():
    asyncio.run(run_cli())

if __name__ == "__main__":
    main()