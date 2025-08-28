# ES-TUI: Everything Search Terminal Interface

A comprehensive terminal user interface for [voidtools Everything Search CLI `es.exe`](https://www.voidtools.com/support/everything/command_line_interface/) that brings powerful file search capabilities to the command line. Built because Windows Explorer's search functionality remains fundamentally broken after decades.

## Why This Exists

Windows File Explorer's search has been unreliable, slow, and feature-poor since its inception. Microsoft has consistently failed to deliver a competent search experience, leaving users frustrated with:

- Inexplicably slow searches on local drives
- Inconsistent indexing that misses files
- Limited search syntax and filtering options
- No regex support or advanced pattern matching
- Poor performance on large directories
- Inability to search file contents reliably

Everything Search by voidtools solves these problems with instant NTFS index-based searching, but lacks a proper terminal interface for power users and automation workflows.

ES-TUI bridges this gap by providing a full-featured terminal interface with modern conveniences.

## Features

### Core Search Capabilities
- **Instant Search**: Leverages Everything's NTFS indexing for sub-second filename/path results
- **Content Search**: Integrated Windows Search for file content using `es_winsearch.py`
- **Hybrid Results**: Combines filename/path results (Everything) with content matches (Windows Search)
- **Advanced Filtering**: Regex, case-sensitive, whole-word, and path matching
- **Rich Search Syntax**: Full Everything command-line syntax support

### User Interface
- **Rich TUI**: Full-screen interface with intuitive keyboard navigation
- **File Type Icons**: Visual indicators with Unicode/ASCII fallback
- **Multiple View Modes**: Customizable columns, sorting, and display options
- **Properties Panel**: Detailed file information with Windows-specific metadata
- **EXIF Integration**: View image metadata with PyExifTool support
- **Keyboard Shortcuts**: Vim-like navigation and standard shortcuts

### Export & Integration
- **Export Support**: Save results in CSV, EFU, TXT, M3U, M3U8 formats
- **Clipboard Integration**: Copy paths, filenames, or directories
- **Debug Mode**: Comprehensive logging for troubleshooting

## Installation

### Prerequisites

Install Everything CLI using your preferred Windows package manager:

**Using Chocolatey:**
```cmd
choco install es -y
```

**Using Winget:**
```cmd
winget install voidtools.Everything.Cli
```

**Using Scoop:**
```cmd
scoop bucket add extras
scoop install everything-cli
```

### Install Python Dependencies

```cmd
# Install required dependencies
pip install pywin32

# Install optional dependencies for enhanced features
pip install pyexiftool windows-curses
```

### Install ES-TUI

```cmd
# Clone the repository
git clone https://github.com/Foadsf/es-tui.git
cd es-tui

# Run ES-TUI
python es_tui.py
```

## Usage

### Basic Usage

```cmd
# Start ES-TUI
python es_tui.py

# Start with initial search query
python es_tui.py --query "*.pdf"

# Enable debug mode
python es_tui.py --debug

# Specify custom es.exe location
python es_tui.py --es-path "C:\path\to\es.exe"

# Specify custom ExifTool location
python es_tui.py --exiftool-path "C:\path\to\exiftool.exe"
```

### Creating Command Aliases

For convenient access, create a command alias using a startup batch file:

**Create `path\to\default.bat`:**
```cmd
@echo off
doskey est=^"path\to\python.exe^" "path\to\es-tui\es_tui.py" --debug $*
```

**Configure Windows Terminal profile:**
- Command line: `%SystemRoot%\System32\cmd.exe /k "path\to\default.bat"`
- This loads your aliases automatically when opening a new terminal

**Usage after setup:**
```cmd
est *.pdf
est --query "readme"
```

### Keyboard Shortcuts

| Key              | Action                          |
| ---------------- | ------------------------------- |
| `F1` / `?`       | Show help                       |
| `F2` / `Ctrl+O`  | Open options                    |
| `F3` / `Ctrl+E`  | Export results                  |
| `F4`             | Advanced search dialog          |
| `F5` / `Ctrl+R`  | New search                      |
| `F6` / `x`       | Show EXIF metadata              |
| `F7`             | Toggle file icons               |
| `F8`             | Toggle Unicode/ASCII icons      |
| `F9`             | Toggle debug mode               |
| `F10` / `Ctrl+Q` | Quit                            |
| `Tab`            | Switch focus (search/results)   |
| `Enter`          | Open selected file              |
| `Space`          | Toggle properties panel         |
| `c`              | Copy path/location to clipboard |
| `↑↓` / `j/k`     | Navigate results                |
| `PgUp/PgDn`      | Scroll by page                  |
| `Home/End`       | Go to first/last result         |

### Search Syntax

ES-TUI supports Everything's full command-line syntax:

```
*.pdf                    # Find all PDF files
size:>1mb               # Files larger than 1MB
dm:today                # Files modified today
regex:\.log$            # Files ending in .log
/ad                     # Folders only
"exact phrase"          # Exact phrase matching in filenames
content:"search text"   # Content search (via Windows Search)
```

## Dual Search Engine Architecture

ES-TUI uses a hybrid approach combining two search engines:

### Everything Search (es.exe)
- **Purpose**: Instant filename and path searches
- **Data Source**: NTFS Master File Table
- **Speed**: Sub-second results
- **Coverage**: All files and folders

### Windows Search (es_winsearch.py)
- **Purpose**: File content and metadata searches
- **Data Source**: Windows Search Index
- **Speed**: Fast for indexed content
- **Coverage**: File contents, properties, metadata

### Result Combination
Results from both engines are concatenated without deduplication, providing comprehensive coverage of both filenames/paths and content matches.

## Configuration

### Search Options
- **Search Modes**: Normal, Regex, Case Sensitive, Whole Word, Match Path
- **Sort Fields**: Name, Size, Date Modified, Path, Extension, Attributes
- **Display Options**: Show/hide columns, icon types, size formats
- **Filters**: Path filters, instance names, result limits

### Advanced Features
- **Properties Panel**: Windows file attributes, ownership, type associations
- **EXIF Viewer**: Image metadata display with PyExifTool
- **Export Formats**: Multiple output formats for automation
- **Debug Logging**: Comprehensive troubleshooting information

## Requirements

- **OS**: Windows 10/11 (primary support)
- **Python**: 3.8 or higher
- **Everything CLI**: 1.4+ (es.exe)
- **Dependencies**: pywin32 (required), pyexiftool (optional), windows-curses (optional)
- **Terminal**: Command Prompt, PowerShell, Windows Terminal, or any terminal with curses support

## Troubleshooting

### Common Issues

**ES.exe not found:**
- Ensure Everything CLI is installed: `choco install es -y`
- Use `--es-path` to specify custom location
- Check common installation paths:
  - `%ProgramFiles%\Everything\es.exe`
  - `%ProgramData%\chocolatey\bin\es.exe`
  - `%LOCALAPPDATA%\Programs\Everything\es.exe`

**Icons not displaying:**
- Try F8 to toggle ASCII mode
- Check terminal Unicode support (Windows Terminal recommended)
- Enable debug mode to see detailed icon rendering logs

**Search returns no results:**
- Verify Everything service is running in Services.msc
- Check Everything's database is built (may take time on first run)
- Try searching in Everything GUI first
- Ensure NTFS drives are indexed in Everything settings

**Windows Search integration fails:**
- Windows Search service must be running
- Files must be indexed by Windows Search for content searching
- Check Windows Search settings in Control Panel
- Use `--debug` to see detailed Windows Search error messages

### Debug Mode

Enable comprehensive logging:
```cmd
python es_tui.py --debug --log-file debug.log
```

Debug mode provides detailed logging for:
- Search command construction and execution
- Icon rendering and terminal capabilities
- File system operations and metadata extraction
- Both Everything and Windows Search interactions
- UI event handling and error conditions

### Windows Terminal Configuration

For optimal Unicode support and icon display:
- Use a font supporting Unicode symbols (Cascadia Code, JetBrains Mono)
- Enable UTF-8 encoding in terminal settings
- Use Windows Terminal for best compatibility

## Contributing

Areas needing development:
- Cross-platform compatibility testing
- Performance optimizations for large result sets
- Additional export formats and integrations
- UI/UX improvements and customization options
- Enhanced Windows-specific features (junction points, NTFS streams)

## License

Released under the MIT License. See `LICENSE` file for details.

## Acknowledgments

- [voidtools](https://www.voidtools.com/) for creating Everything Search and its CLI
- The Python curses community for terminal UI guidance
- Windows power users frustrated with Explorer's persistent search failures
