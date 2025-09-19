# Security Policy

Win Sayver takes security seriously. We appreciate your efforts to responsibly disclose security vulnerabilities.

## Supported Versions

We currently support the following versions with security updates:

| Version | Supported          |
| ------- | ------------------ |
| 3.1.x   | :white_check_mark: |
| 3.0.x   | :white_check_mark: |
| < 3.0   | :x:                |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

### What to include in your report

Please include the following information in your security report:

- **Type of issue** (e.g., buffer overflow, SQL injection, cross-site scripting, etc.)
- **Full paths of source file(s) related to the manifestation of the issue**
- **The location of the affected source code** (tag/branch/commit or direct URL)
- **Any special configuration required to reproduce the issue**
- **Step-by-step instructions to reproduce the issue**
- **Proof-of-concept or exploit code** (if possible)
- **Impact of the issue**, including how an attacker might exploit the issue

This information will help us triage your report more quickly.

### Response Timeline

- **Initial Response**: We will acknowledge your email within 48 hours
- **Status Update**: We will provide a detailed response indicating the next steps within 7 days
- **Resolution**: We aim to resolve critical security issues within 30 days

### Security Update Process

1. **Confirmation**: We will confirm the vulnerability and determine its severity
2. **Fix Development**: We will develop and test a fix
3. **Release**: We will release a security update
4. **Disclosure**: We will publicly disclose the vulnerability after the fix is released

## Security Features

Win Sayver implements several security measures:

### API Key Protection
- API keys are encrypted using Fernet (symmetric encryption)
- Keys are never logged or stored in plain text
- Secure key storage in user's local encrypted configuration

### Image Processing Security
- Multi-level image validation before AI analysis
- File type verification using both headers and extensions
- Size limits to prevent memory exhaustion attacks
- Sanitization of file paths to prevent directory traversal

### System Information Security
- No collection of personally identifiable information (PII)
- System profiling limited to technical specifications only
- No network credentials or passwords collected
- Local processing with minimal external communication

### Network Security
- All API communications use HTTPS with certificate verification
- Request timeout limits to prevent hanging connections
- Rate limiting implementation for API calls
- Input validation for all external data

## Best Practices for Users

1. **Keep Win Sayver Updated**: Always use the latest version
2. **Protect API Keys**: Never share your Google API keys
3. **Secure Screenshots**: Be mindful of sensitive information in screenshots
4. **System Access**: Run with minimal required privileges
5. **Firewall**: Consider restricting network access if needed

## Security Considerations for Contributors

When contributing to Win Sayver, please:

1. **Review our coding standards** in `RULTE.md` for security guidelines
2. **Test security features** thoroughly before submitting PRs
3. **Validate inputs** from all external sources (files, network, user input)
4. **Use secure coding practices** outlined in our contribution guidelines
5. **Report security concerns** during code review process

## Third-Party Dependencies

We regularly update and monitor our dependencies for security vulnerabilities:

- **Automated dependency scanning** in our CI/CD pipeline
- **Regular security updates** for all third-party packages
- **Vulnerability alerts** configured for the repository
- **Security testing** included in our test suite

## Security Tools

Our development process includes:

- **Static code analysis** with security-focused linters
- **Dependency vulnerability scanning** 
- **Automated security testing** in CI/CD
- **Code quality checks** including security patterns
- **Pre-commit hooks** for security validation

## Disclosure Policy

When we receive a security bug report, we will:

1. Confirm the problem and determine the affected versions
2. Audit code to find any potential similar problems
3. Prepare fixes for all supported versions
4. Release new versions with security patches
5. Publicly announce the security issue after fixes are deployed

## Recognition

We appreciate the security research community's efforts. Security researchers who responsibly report vulnerabilities will be:

- **Acknowledged** in our security advisories (unless they prefer to remain anonymous)
- **Credited** in our release notes and changelog
- **Listed** in our contributors if they choose

## Contact Information

- **Security Email**: security@winsayver.com
- **General Support**: contact@winsayver.com
- **Project Repository**: https://github.com/zSayf/Win-Sayver

---

*This security policy is effective as of the date of the latest commit to this file and supersedes any previous security policies.*
