#!/usr/bin/env python3
"""
Setup script for Win Sayver - AI-Powered Windows Troubleshooting Assistant
"""

from setuptools import setup, find_packages
from pathlib import Path
import re

# Read README file
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding='utf-8')

# Read requirements from win_sayver_poc/requirements.txt
requirements_file = this_directory / "win_sayver_poc" / "requirements.txt"
requirements = []
if requirements_file.exists():
    with open(requirements_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                # Clean up version constraints for setup.py
                if line.startswith('google-genai'):
                    requirements.append('google-generativeai>=0.8.0')
                elif line.startswith('PyQt6'):
                    requirements.append('PyQt6>=6.4.2')
                else:
                    requirements.append(line)

# Extract version from main_gui.py or define it here
VERSION = "3.1.0"

setup(
    name="win-sayver",
    version=VERSION,
    author="Win Sayver Team",
    author_email="contact@winsayver.com",
    description="AI-Powered Windows Troubleshooting Assistant with Google Gemini 2.5 Pro",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/zSayf/Win-Sayver",
    packages=find_packages(where="win_sayver_poc"),
    package_dir={"": "win_sayver_poc"},
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: End Users/Desktop",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: Microsoft :: Windows :: Windows 10",
        "Operating System :: Microsoft :: Windows :: Windows 11",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: System :: Systems Administration",
        "Topic :: System :: Monitoring",
        "Topic :: Utilities",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Environment :: Win32 (MS Windows)",
        "Natural Language :: English",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        'console_scripts': [
            'win-sayver=main_gui:main',
            'winsayver=main_gui:main',
        ],
    },
    include_package_data=True,
    package_data={
        '': [
            '*.md', '*.txt', '*.bat', '*.rst',
            'docs/*', 'templates/*', 'assets/*'
        ],
    },
    keywords=[
        "windows", "troubleshooting", "ai", "gemini", "diagnostics", 
        "system-analysis", "automation", "artificial-intelligence",
        "desktop-application", "pyqt6", "windows-management"
    ],
    project_urls={
        "Bug Reports": "https://github.com/zSayf/Win-Sayver/issues",
        "Source": "https://github.com/zSayf/Win-Sayver",
        "Documentation": "https://github.com/zSayf/Win-Sayver/wiki",
        "Changelog": "https://github.com/zSayf/Win-Sayver/blob/main/CHANGELOG.md",
        "Funding": "https://github.com/sponsors/zSayf",
    },
    extras_require={
        'dev': [
            'pytest>=7.4.0',
            'pytest-cov>=4.1.0',
            'pytest-qt>=4.2.0',
            'flake8>=6.0.0',
            'black>=23.0.0',
            'mypy>=1.5.0',
            'pre-commit>=3.3.0',
        ],
        'build': [
            'pyinstaller>=5.13.0',
            'setuptools>=68.0.0',
            'wheel>=0.41.0',
            'build>=0.10.0',
        ]
    },
    zip_safe=False,
)