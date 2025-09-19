# Frequently Asked Questions (FAQ)

Find quick answers to common questions about Win Sayver v3.1.0.

## 🚀 General Questions

### What is Win Sayver?
Win Sayver is an AI-powered Windows troubleshooting assistant that analyzes error screenshots and provides intelligent solutions. It combines system profiling with Google's Gemini AI to offer personalized troubleshooting guidance.

### What Windows versions are supported?
Win Sayver supports:
- Windows 10 (version 1909 and later)
- Windows 11 (all versions)

### Is Win Sayver free to use?
Yes, Win Sayver is completely free and open-source. However, you need your own Google Gemini API key for AI analysis (Google provides free tier usage).

### How does Win Sayver protect my privacy?
- Screenshots are processed locally; only metadata is sent to AI
- Your API key is encrypted using Fernet encryption
- No personal data is transmitted without your consent
- All network communication uses HTTPS encryption

## 🔑 API Key & Setup

### How do I get a Gemini API key?
1. Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Sign in with your Google account
3. Click "Create API Key"
4. Copy and paste it into Win Sayver's settings

### Is the Gemini API free?
Yes, Google provides a generous free tier for Gemini API:
- 15 requests per minute
- 1,500 requests per day
- 1 million tokens per month

For most users, this is more than sufficient.

### My API key isn't working. What should I check?
1. **Verify the key**: Ensure you copied it completely
2. **Check billing**: Ensure your Google Cloud account has billing enabled
3. **API access**: Confirm Gemini API is enabled in your Google Cloud Console
4. **Regenerate**: Try generating a new API key

### Can I use Win Sayver without an API key?
No, the AI analysis requires a valid Gemini API key. However, you can still use the system profiling features without one.

## 📷 Screenshot Analysis

### What image formats are supported?
Win Sayver supports:
- PNG (recommended for best quality)
- JPEG/JPG
- BMP
- GIF (static images)
- Maximum file size: 10MB

### Why is my screenshot analysis not accurate?
**Common issues:**
- **Low resolution**: Use high-quality screenshots
- **Missing error text**: Ensure error messages are clearly visible
- **Lack of context**: Include relevant UI elements and system information
- **Compressed images**: Avoid heavily compressed JPEG files

### How long does analysis take?
Typically 10-30 seconds, depending on:
- Screenshot complexity
- Internet connection speed
- Google API response time
- System profile completeness

### Can I analyze multiple screenshots at once?
Yes, Win Sayver supports batch processing. Upload multiple screenshots and get a combined analysis report.

## 🔧 Technical Issues

### Win Sayver won't start. What should I do?
1. **Run as administrator**: Right-click and "Run as administrator"
2. **Check antivirus**: Temporarily disable antivirus software
3. **Reinstall**: Uninstall and reinstall Win Sayver
4. **Dependencies**: Ensure all Python dependencies are installed

### I'm getting "Permission Denied" errors.
**Solutions:**
- Run Win Sayver as administrator
- Check Windows Defender exclusions
- Verify user account has necessary permissions
- Temporarily disable antivirus during system scans

### The system profile scan is taking too long.
**Troubleshooting:**
- Close unnecessary applications
- Run Windows Memory Diagnostic
- Check for Windows updates
- Restart your computer and try again

### Win Sayver crashes when analyzing screenshots.
**Debugging steps:**
1. Check Windows Event Viewer for error details
2. Update graphics drivers
3. Reduce screenshot file size
4. Report the issue with crash logs

## 💻 System Requirements

### What are the minimum system requirements?
- **OS**: Windows 10 (1909+) or Windows 11
- **RAM**: 4 GB minimum, 8 GB recommended
- **Storage**: 500 MB free space
- **Python**: 3.8+ (for source installation)
- **Internet**: Active connection for AI analysis

### Will Win Sayver slow down my computer?
No, Win Sayver is designed to be lightweight:
- Minimal CPU usage when idle
- System profiling uses background processes
- Memory usage typically under 100MB
- No impact on system performance

### Can I run Win Sayver on older computers?
Yes, but ensure:
- At least 4 GB RAM available
- Updated Windows version
- Stable internet connection
- Modern graphics drivers

## 🛡️ Security & Privacy

### What data does Win Sayver collect?
Win Sayver collects:
- **System specifications** (CPU, RAM, OS version)
- **Installed software** (for compatibility analysis)
- **Error screenshots** (processed locally)
- **Usage analytics** (optional, can be disabled)

### Is my data sent to third parties?
Only anonymous metadata is sent to Google's Gemini AI for analysis. Personal information, file contents, and system credentials are never transmitted.

### How secure is my API key storage?
Your API key is:
- Encrypted using Fernet (AES 128-bit encryption)
- Stored locally on your computer
- Never transmitted in plain text
- Automatically secured on first use

### Can I use Win Sayver offline?
No, Win Sayver requires internet connectivity for:
- AI analysis via Gemini API
- System update checks
- Solution database updates

However, system profiling works offline.

## 🔄 Updates & Maintenance

### How do I update Win Sayver?
**Executable version:**
- Download latest installer from GitHub Releases
- Run installer to update automatically

**Pip installation:**
```bash
pip install --upgrade win-sayver
```

**Source installation:**
```bash
git pull origin main
pip install -r requirements.txt --upgrade
```

### How often should I update?
We recommend updating:
- **Major releases**: Immediately (new features, security fixes)
- **Minor updates**: Within a week (bug fixes, improvements)
- **Patch releases**: When convenient (small fixes)

### Will updates affect my settings?
No, your settings are preserved during updates:
- API key configuration
- User preferences
- Solution history
- Custom profiles

## 🐛 Common Error Messages

### "API Rate Limit Exceeded"
**Cause**: Too many requests in a short time
**Solution**: Wait 1 minute and try again, or upgrade your Google Cloud plan

### "Invalid Image Format"
**Cause**: Unsupported file type or corrupted image
**Solution**: Convert to PNG/JPEG or retake the screenshot

### "System Profile Failed"
**Cause**: Insufficient permissions or system resources
**Solution**: Run as administrator, close other programs

### "Network Connection Error"
**Cause**: Internet connectivity issues
**Solutions**:
- Check internet connection
- Verify firewall settings
- Try different network
- Contact your ISP if problems persist

### "Analysis Timeout"
**Cause**: Request took too long to process
**Solutions**:
- Reduce screenshot size
- Check internet speed
- Retry the analysis
- Report persistent issues

## 🎯 Best Practices

### For Better Analysis Results
1. **Clear screenshots**: Include complete error messages
2. **Context matters**: Show relevant UI elements
3. **Updated system**: Keep system profile current
4. **One issue at a time**: Analyze individual problems
5. **Follow solutions carefully**: Apply fixes step-by-step

### For System Performance
1. **Regular updates**: Keep Win Sayver updated
2. **Clean screenshots**: Remove unnecessary visual clutter
3. **Stable internet**: Use reliable network connection
4. **System maintenance**: Run Windows updates regularly

### For Security
1. **Protect API key**: Never share your Gemini API key
2. **System backups**: Create restore points before major changes
3. **Verify solutions**: Test fixes in safe environment first
4. **Regular scans**: Keep antivirus software updated

## 📞 Getting More Help

If your question isn't answered here:

### 🌐 Community Support
- **GitHub Discussions**: Ask questions and share solutions
- **Issue Tracker**: Report bugs and feature requests
- **Community Wiki**: User-contributed guides and tips

### 📧 Direct Support
- **In-app feedback**: Use the built-in feedback feature
- **Email support**: Contact through GitHub profile
- **Discord community**: Join our troubleshooting community

### 📚 Additional Resources
- **User Guide**: Comprehensive feature documentation
- **Installation Guide**: Detailed setup instructions
- **GitHub Repository**: Source code and technical documentation
- **Release Notes**: Latest features and changes

---

**Still have questions?** Don't hesitate to reach out to our community or create an issue on GitHub. We're here to help make your Windows troubleshooting experience as smooth as possible!

**Win Sayver v3.1.0** - Your intelligent Windows troubleshooting companion.