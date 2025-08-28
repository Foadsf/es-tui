# ES-TUI: Everything Search Terminal Interface

A comprehensive terminal user interface for [Everything Search](https://www.voidtools.com/) that brings powerful file search capabilities to the command line. Built because Windows Explorer's search functionality remains fundamentally broken after decades.

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

- **Instant Search**: Leverages Everything's NTFS indexing for sub-second results
- **Rich TUI**: Full-screen interface with intuitive keyboard navigation
- **File Type Icons**: Visual indicators for different file types (Unicode/ASCII fallback)
- **Multiple View Modes**: Customizable columns, sorting, and display options
- **Advanced Filtering**: Regex, case-sensitive, whole-word, and path matching
- **Properties Panel**: Detailed file information with Windows-specific metadata
- **Export Support**: Save results in CSV, EFU, TXT, M3U, M3U8 formats
- **EXIF Integration**: View image metadata with PyExifTool support
- **Keyboard Shortcuts**: Vim-like navigation and standard shortcuts
- **Debug Mode**: Comprehensive logging for troubleshooting

## Installation

### Prerequisites

Install using your preferred Windows package manager:

**Using Chocolatey:**
```cmd
# Install Everything Search CLI
choco install es -y

# Install Python 3.8+
choco install python

# Install Git (if needed)
choco install git
```

**Using Winget:**
```cmd
# Install Everything Search
winget install voidtools.Everything

# Install Python 3.8+
winget install Python.Python.3.12

# Install Git (if needed)
winget install Git.Git
```

**Using Scoop:**
```cmd
# Add extras bucket for Everything
scoop bucket add extras

# Install Everything Search
scoop install everything

# Install Python 3.8+
scoop install python

# Install Git (if needed)
scoop install git
```

### Install ES-TUI

**Command Prompt (cmd):**
```cmd
# Clone the repository
git clone https://github.com/Foadsf/es-tui.git
cd es-tui

# Install optional dependencies for EXIF support
pip install pyexiftool windows-curses

# Run ES-TUI
python es_tui.py
```

**PowerShell:**
```powershell
# Clone the repository
git clone https://github.com/Foadsf/es-tui.git
Set-Location es-tui

# Install optional dependencies for EXIF support
pip install pyexiftool windows-curses

# Run ES-TUI
python es_tui.py
```

## Usage

### Basic Usage

**Command Prompt:**
```cmd
# Start ES-TUI
python es_tui.py

# Start with initial search query
python es_tui.py --query "*.pdf"

# Enable debug mode
python es_tui.py --debug

# Specify custom es.exe location
python es_tui.py --es-path "C:\ProgramData\chocolatey\bin\es.exe"
```

**PowerShell:**
```powershell
# Start ES-TUI
python es_tui.py

# Start with initial search query
python es_tui.py --query "*.pdf"

# Enable debug mode
python es_tui.py --debug

# Specify custom es.exe location
python es_tui.py --es-path "C:\ProgramData\chocolatey\bin\es.exe"
```

### Keyboard Shortcuts

| Key              | Action                        |
| ---------------- | ----------------------------- |
| `F1` / `?`       | Show help                     |
| `F2` / `Ctrl+O`  | Open options                  |
| `F3` / `Ctrl+E`  | Export results                |
| `F5` / `Ctrl+R`  | New search                    |
| `F6` / `x`       | Show EXIF metadata            |
| `F7`             | Toggle icons                  |
| `F8`             | Toggle Unicode/ASCII icons    |
| `F10` / `Ctrl+Q` | Quit                          |
| `Tab`            | Switch focus (search/results) |
| `Enter`          | Open selected file            |
| `Space`          | Toggle properties panel       |
| `↑↓` / `j/k`     | Navigate results              |
| `PgUp/PgDn`      | Scroll by page                |
| `Home/End`       | Go to first/last result       |

### Search Syntax

ES-TUI supports Everything's full search syntax:

```
*.pdf                    # Find all PDF files
size:>1mb               # Files larger than 1MB
dm:today                # Files modified today
regex:\.log$            # Files ending in .log
folder: /a              # Folders only
"exact phrase"          # Exact phrase matching
```

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
- **Everything**: 1.4+ recommended
- **Terminal**: Command Prompt, PowerShell, Windows Terminal, or any terminal with curses support
- **Optional**: PyExifTool for image metadata, ExifTool binary

## Troubleshooting

### Common Issues

**Icons not displaying:**
- Try F8 to toggle ASCII mode
- Check terminal Unicode support (Windows Terminal recommended)
- Enable debug mode to see detailed icon rendering logs

**ES.exe not found:**
- Ensure Everything is installed and `es.exe` is in PATH
- Use `--es-path` to specify custom location
- Check common installation paths:
  - `%ProgramFiles%\Everything\es.exe`
  - `%ProgramFiles(x86)%\Everything\es.exe`
  - `%LOCALAPPDATA%\Programs\Everything\es.exe`
  - `%ProgramData%\chocolatey\bin\es.exe`

**Search returns no results:**
- Verify Everything service is running in Services.msc
- Check Everything's database is built (may take time on first run)
- Try searching in Everything GUI first
- Ensure NTFS drives are indexed in Everything settings

**Performance issues:**
- Reduce max results in options (F2)
- Check Everything's database size and indexing status
- Enable debug mode to identify bottlenecks
- Consider excluding network drives from Everything indexing

### Debug Mode

**Command Prompt:**
```cmd
python es_tui.py --debug --log-file debug.log
```

**PowerShell:**
```powershell
python es_tui.py --debug --log-file debug.log
```

Debug mode provides detailed logging for:
- Icon rendering issues
- Terminal capability detection
- Search command construction
- File system operations
- Everything service communication

### Windows Terminal Configuration

For best Unicode support and icon display, use Windows Terminal with:
- A font that supports Unicode symbols (Cascadia Code, JetBrains Mono)
- UTF-8 encoding enabled
- Hardware acceleration enabled

## Contributing

Contributions welcome! Areas needing work:

- Cross-platform compatibility testing (Linux/macOS)
- Additional export formats
- Performance optimizations
- UI/UX improvements
- Documentation and examples
- Windows-specific features (junction points, NTFS streams)

## License

Released under the MIT License. See `LICENSE` file for details.

## Acknowledgments

- [voidtools](https://www.voidtools.com/) for creating Everything Search
- The Python curses community for terminal UI guidance
- Windows power users frustrated with Explorer's search failures
- Package maintainers for Chocolatey, Winget, and Scoop
