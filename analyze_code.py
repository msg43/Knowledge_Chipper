import os

# --- Configuration ---
# The root directory to start scanning from. '.' means the current directory.
ROOT_DIR = "."

# The name of the markdown file to save the report to.
OUTPUT_FILENAME = "code_analysis_report.md"

# Add or remove file extensions to be considered "code files".
# I've removed '.md' as requested.
CODE_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".java",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".cs",
    ".go",
    ".rs",
    ".swift",
    ".kt",
    ".scala",
    ".rb",
    ".php",
    ".html",
    ".css",
    ".scss",
    ".less",
    ".vue",
    ".svelte",
    ".sh",
    ".R",
}

# Add directory names to this set to exclude them from the analysis.
IGNORE_DIRS = {
    "node_modules",
    ".git",
    "__pycache__",
    "venv",
    ".venv",
    "env",
    ".vscode",
    ".idea",
}
# --- End Configuration ---


def get_file_stats(filepath):
    """Calculates the line count and size of a single file."""
    try:
        with open(filepath, encoding="utf-8", errors="ignore") as f:
            lines = len(f.readlines())
        size = os.path.getsize(filepath)
        return lines, size
    except Exception:
        return 0, 0


def analyze_directory(root_dir):
    """Analyzes all code files in a directory and its subdirectories."""
    file_stats = []
    total_lines = 0
    total_size = 0

    for dirpath, dirnames, filenames in os.walk(root_dir):
        # This line prevents the script from entering ignored directories
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]

        for filename in filenames:
            if any(filename.endswith(ext) for ext in CODE_EXTENSIONS):
                filepath = os.path.join(dirpath, filename)
                lines, size = get_file_stats(filepath)

                if lines > 0 or size > 0:
                    file_stats.append(
                        {
                            "path": os.path.relpath(filepath, root_dir),
                            "lines": lines,
                            "size": size,
                        }
                    )
                    total_lines += lines
                    total_size += size

    return file_stats, total_lines, total_size


def format_size(size_bytes):
    """Formats size in bytes to a more readable format (KB, MB, GB)."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024**2:
        return f"{size_bytes/1024:.2f} KB"
    elif size_bytes < 1024**3:
        return f"{size_bytes/1024**2:.2f} MB"
    else:
        return f"{size_bytes/1024**3:.2f} GB"


def main():
    """Main function to run the analysis and write the report to a file."""
    file_stats, total_lines, total_size = analyze_directory(ROOT_DIR)

    # Sort files by line count in descending order
    file_stats.sort(key=lambda x: x["lines"], reverse=True)

    # Build the report content as a list of strings
    report_content = []
    report_content.append("# Code Analysis Report")
    report_content.append("\n## Summary\n")
    report_content.append(f"- **Total Code Files Found:** {len(file_stats)}")
    report_content.append(f"- **Total Lines of Code:**    {total_lines}")
    report_content.append(f"- **Total Size of Code:**     {format_size(total_size)}")
    report_content.append("\n## All Files by Line Count\n")
    report_content.append("| # | File Path | Lines | Size |")
    report_content.append("|---|-----------|-------|------|")

    # Add all files to the report
    for i, stat in enumerate(file_stats):
        report_content.append(
            f"| {i+1} | {stat['path']} | {stat['lines']} | {format_size(stat['size'])} |"
        )

    # Write the report to the specified markdown file
    try:
        with open(OUTPUT_FILENAME, "w", encoding="utf-8") as f:
            f.write("\n".join(report_content))
        print(f"Report successfully written to {OUTPUT_FILENAME}")
    except OSError as e:
        print(f"Error writing report to file: {e}")


if __name__ == "__main__":
    main()
