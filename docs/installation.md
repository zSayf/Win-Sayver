# Installation Guide

This guide will help you install Win Sayver v3.1.0 on your Windows system and get it configured for optimal performance.

## 📋 System Requirements

### Minimum Requirements
- **Operating System**: Windows 10 (1909 or later) or Windows 11
- **Python**: Python 3.8 or higher (if installing from source/pip)
- **RAM**: 4 GB RAM minimum, 8 GB recommended
- **Storage**: 500 MB free disk space
- **Internet**: Active internet connection for AI analysis

### Recommended Requirements
- **Operating System**: Windows 11 (latest version)
- **Python**: Python 3.11 or 3.12
- **RAM**: 8 GB RAM or higher
- **Storage**: 1 GB free disk space
- **Internet**: Stable broadband connection

## 🚀 Installation Methods

### Method 1: Executable Installer (Recommended)

1. **Download the Installer**
   - Visit the [Releases page](https://github.com/zSayf/Win-Sayver/releases)
   - Download the latest `WinSayver-v3.1.0-installer.exe`

2. **Run the Installer**
   - Right-click the installer and select "Run as administrator"
   - Follow the installation wizard
   - Choose your installation directory (default: `C:\Program Files\Win Sayver`)

3. **Launch Win Sayver**
   - Find Win Sayver in your Start Menu
   - Or double-click the desktop shortcut

### Method 2: Portable Executable

1. **Download Portable Version**
   - Download `WinSayver-v3.1.0-portable.zip`
   - Extract to your preferred directory

2. **Run Win Sayver**
   - Navigate to the extracted folder
   - Double-click `WinSayver.exe`

### Method 3: Install via pip

```bash
# Install from PyPI (when available)
pip install win-sayver

# Or install from GitHub
pip install git+https://github.com/zSayf/Win-Sayver.git

# Run Win Sayver
win-sayver
```

### Method 4: Install from Source

```bash
# Clone the repository
git clone https://github.com/zSayf/Win-Sayver.git
cd Win-Sayver

# Create virtual environment (recommended)
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install in development mode
pip install -e .

# Run Win Sayver
python -m win_sayver
```

## 🔑 API Key Configuration

Win Sayver requires a Google Gemini API key for AI-powered analysis.

### Getting Your API Key

1. Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Sign in with your Google account
3. Click "Create API Key"
4. Copy your API key (keep it secure!)

### Setting Up the API Key

#### Method 1: Through the GUI (Recommended)
1. Launch Win Sayver
2. Go to **Settings** → **API Configuration**
3. Paste your API key in the "Gemini API Key" field
4. Click **Save** (key will be encrypted automatically)

#### Method 2: Environment Variable
```bash
# Set environment variable (Windows Command Prompt)
set GEMINI_API_KEY=your_api_key_here

# Set environment variable (PowerShell)
$env:GEMINI_API_KEY="your_api_key_here"
```

#### Method 3: Configuration File
Create `config.json` in the Win Sayver directory:
```json
{
    "gemini_api_key": "your_api_key_here"
}
```

## ✅ Verification

### Test Your Installation

1. **Launch Win Sayver**
2. **Check System Status**
   - Look for green indicators in the status bar
   - Verify "AI Service: Connected"

3. **Test Screenshot Analysis**
   - Take a test screenshot
   - Upload it to Win Sayver
   - Verify you receive AI analysis results

### Troubleshooting Installation Issues

#### Python Not Found
```bash
# Install Python from Microsoft Store or python.org
winget install Python.Python.3.11
```

#### Permission Errors
- Run installer as administrator
- Check Windows Defender exclusions
- Temporarily disable antivirus during installation

#### API Key Issues
- Verify your API key is valid
- Check your Google Cloud billing settings
- Ensure you have Gemini API access enabled

#### Dependencies Failed
```bash
# Update pip and try again
python -m pip install --upgrade pip
pip install -r requirements.txt --force-reinstall
```

## 🔒 Security Considerations

- Your API key is encrypted using Fernet encryption
- Screenshots are processed locally and only metadata is sent to AI
- No personal data is transmitted without your consent
- All network communication uses HTTPS

## 🔄 Updating Win Sayver

### Executable Installation
1. Download the latest installer
2. Run it to update automatically

### Pip Installation
```bash
pip install --upgrade win-sayver
```

### Source Installation
```bash
git pull origin main
pip install -r requirements.txt --upgrade
```

## 🗑️ Uninstallation

### Executable Installation
1. Go to **Settings** → **Apps**
2. Search for "Win Sayver"
3. Click **Uninstall**

### Pip Installation
```bash
pip uninstall win-sayver
```

### Manual Cleanup
Remove these directories if they exist:
- `%APPDATA%\WinSayver`
- `%LOCALAPPDATA%\WinSayver`

---

**Next Steps**: Once installed, check out the [User Guide](user-guide.md) to learn how to use Win Sayver effectively!