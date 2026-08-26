import os
import sys
import argparse
import json
from pathlib import Path
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.tree import Tree
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.downloader import download_reel, extract_reel_id
from src.transcribe import transcribe_audio
from src.extractor import extract_workout_program
from src.schema import WorkoutProgram

# Load environment variables (.env.local first, then .env)
load_dotenv(".env.local")
load_dotenv(".env")

console = Console()


def print_hierarchical_program(program: WorkoutProgram, reel_id: str, model_used: str):
    console.print("\n")
    header_text = (
        f"[bold cyan]{program.title}[/bold cyan] [dim]({program.program_id})[/dim]\n"
        f"[yellow]Split Architecture:[/yellow] [bold]{program.split_type.value}[/bold]\n"
        f"[blue]Cycle Frequency:[/blue] {program.cycle_frequency}\n"
        f"[green]Overview:[/green] {program.overview}\n"
        f"[magenta]AI Engine:[/magenta] [bold]{model_used}[/bold] | "
        f"[magenta]Confidence Score:[/magenta] {program.audit.confidence_score * 100:.1f}%"
    )
    console.print(
        Panel(
            header_text,
            title=f"🏋️ Hierarchical Workout Program ({reel_id})",
            border_style="cyan",
        )
    )

    # Days Breakdown
    for day in program.days:
        day_panel_text = (
            f"[bold yellow]Focus:[/bold yellow] {day.day_focus}\n"
            f"[bold green]Target Muscles:[/bold green] {', '.join(day.target_muscle_groups)}"
        )
        console.print(
            Panel(
                day_panel_text,
                title=f"📅 Day {day.day_number}: {day.day_title}",
                border_style="bright_blue",
            )
        )

        for group in day.exercise_groups:
            region_str = f" - {group.target_region}" if group.target_region else ""
            table = Table(
                title=f"🔹 {group.category.value}{region_str}",
                show_header=True,
                header_style="bold magenta",
            )
            table.add_column("Exercise", style="bold white", width=28)
            table.add_column("Equipment", style="cyan", width=14)
            table.add_column("Target Muscle", style="green", width=20)
            table.add_column("Prescribed Volume", style="bold yellow", width=18)
            table.add_column("Coaching Cues & Tips", style="white")

            for ex in group.exercises:
                main_tag = " ⭐ [bold]MAIN[/bold]\n" if ex.is_main_lift else ""
                name_display = f"{main_tag}{ex.canonical_name_ko}\n[dim]{ex.canonical_name_en}[/dim]"

                equip_display = ex.equipment.value.split(" ")[0]

                secondaries = f"\n[dim]+ {', '.join(ex.secondary_muscles)}[/dim]" if ex.secondary_muscles else ""
                muscle_display = f"{ex.primary_muscle}{secondaries}"

                vol = ex.volume
                sets_str = f"{vol.min_sets} sets" if vol.min_sets == vol.max_sets else f"{vol.min_sets}-{vol.max_sets} sets"
                reps_str = f"{vol.min_reps} reps" if vol.min_reps == vol.max_reps else (
                    f"{vol.min_reps}-{vol.max_reps} reps" if vol.max_reps else f"{vol.min_reps}+ reps"
                )
                rest_str = f"\n[dim]Rest: {vol.rest_seconds}s[/dim]" if vol.rest_seconds else ""
                vol_display = f"{sets_str} × {reps_str}{rest_str}"

                cues_list = [f"• {c}" for c in ex.guide.form_cues]
                if ex.guide.common_mistakes_to_avoid:
                    cues_list.append(f"[red]⚠️ Avoid:[/red] {', '.join(ex.guide.common_mistakes_to_avoid)}")
                cues_display = "\n".join(cues_list) if cues_list else "[dim]None[/dim]"

                table.add_row(
                    name_display,
                    equip_display,
                    muscle_display,
                    vol_display,
                    cues_display,
                )

            console.print(table)
            console.print("")

    # Progression Rules
    prog = program.progression
    prog_text = (
        f"[bold cyan]Overload Strategy:[/bold cyan] {prog.overload_strategy}\n"
        f"[bold green]Frequency Schedule:[/bold green] {prog.frequency_schedule}"
    )
    if prog.recovery_guidance:
        prog_text += f"\n[bold yellow]Recovery Guidance:[/bold yellow] {prog.recovery_guidance}"

    console.print(
        Panel(
            prog_text,
            title="📈 Progressive Overload & Program Rules",
            border_style="magenta",
        )
    )

    # Data Quality & Action Items for Mobile App
    audit = program.audit
    audit_flags = []
    if audit.sets_ambiguous:
        audit_flags.append("[yellow]Sets range specified (user selection)[/yellow]")
    if audit.weight_missing:
        audit_flags.append("[red]Weight guidance missing[/red]")
    if audit.rest_missing:
        audit_flags.append("[yellow]Rest interval not stated[/yellow]")

    actions_text = "\n".join([f"  {i+1}. [bold white]{action}[/bold white]" for i, action in enumerate(audit.user_action_items)])
    audit_panel_text = (
        f"[bold]Quality Status:[/bold] {', '.join(audit_flags) if audit_flags else 'All variables resolved'}\n"
        f"[bold]Audit Notes:[/bold] {audit.audit_notes}\n\n"
        f"[bold green]📱 Mobile UI User Action Items (to confirm before starting):[/bold green]\n"
        f"{actions_text if actions_text else '  • No action required'}"
    )

    console.print(
        Panel(
            audit_panel_text,
            title="🔍 Data Quality Audit & Mobile Action Items",
            border_style="yellow",
        )
    )


def analyze_reel(url: str, model: str = "o3-mini", output_dir: str = "output") -> WorkoutProgram:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        console.print("[bold red]Error: OPENAI_API_KEY not found in environment or .env.local![/bold red]")
        sys.exit(1)

    reel_id = extract_reel_id(url)
    console.print(f"\n[bold green]🚀 Launching Hierarchical Workout Pipeline for:[/bold green] [underline cyan]{url}[/underline cyan]")
    console.print(f"[dim]Engine: [bold cyan]{model}[/bold cyan] | Target: [bold white]WorkoutProgram Domain Model[/bold white][/dim]\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # Stage 1: Download & Ingestion
        task1 = progress.add_task("[yellow]Stage 1/4: Ingesting Reel video/audio via yt-dlp...", total=None)
        download_result = download_reel(url)
        progress.update(task1, description="[green]Stage 1/4: Ingestion complete!")

        # Stage 2: STT Transcription
        task2 = progress.add_task("[yellow]Stage 2/4: Transcribing speech with OpenAI Whisper...", total=None)
        transcript = ""
        if download_result.download_success and download_result.audio_path:
            try:
                transcript = transcribe_audio(download_result.audio_path, api_key=api_key)
                progress.update(task2, description="[green]Stage 2/4: Whisper STT transcription finished!")
            except Exception as e:
                progress.update(task2, description=f"[red]Stage 2/4: Whisper STT failed ({e}), using caption...")
        else:
            progress.update(task2, description="[yellow]Stage 2/4: No audio file, continuing with caption...")

        # Stage 3 & 4: Hierarchical Multi-Role Reasoning
        task3 = progress.add_task(f"[yellow]Stage 3-4/4: Multi-Role Sequential Reasoning ({model})...", total=None)
        program = extract_workout_program(
            transcript=transcript,
            caption=download_result.caption,
            uploader=download_result.uploader,
            api_key=api_key,
            model=model,
        )
        progress.update(task3, description=f"[green]Stage 3-4/4: Hierarchical WorkoutProgram generated via {model}!")

    # Display results
    print_hierarchical_program(program, reel_id, model)

    # Save to output file
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{reel_id}_program.json"

    full_output = {
        "url": url,
        "reel_id": reel_id,
        "model_used": model,
        "uploader": download_result.uploader,
        "caption": download_result.caption,
        "transcript": transcript,
        "workout_program": program.model_dump(),
    }

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(full_output, f, ensure_ascii=False, indent=2)

    console.print(f"\n[bold green]💾 Complete relational program JSON saved to:[/bold green] [cyan]{out_file}[/cyan]\n")
    return program


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hierarchical Instagram Reels Workout Extraction Pipeline")
    parser.add_argument(
        "url",
        nargs="?",
        default="https://www.instagram.com/reel/DccqEKJPPqR/",
        help="Instagram Reel URL",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("OPENAI_MODEL", "o3-mini"),
        help="OpenAI Model to use (e.g., o3-mini, gpt-4o)",
    )
    args = parser.parse_args()

    analyze_reel(args.url, model=args.model)
