# Email MCP Server

This MCP (Model Context Protocol) server lets your AI assistant send emails for you.

## What Can It Do?

Your AI assistant can:

- Send both plain text and HTML emails
- Attach files and documents
- Send to multiple people with CC/BCC
- Check if your email setup works

## Available Tools

### `send_email` - Simple Email Sending
Send emails quickly using your environment configuration:
- Just specify recipient, subject, and body
- Automatically uses your configured SMTP settings
- Perfect for quick messages

### `send_custom_email` - Advanced Email Features
Send emails with full control:
- Send to multiple people with CC/BCC
- Add file attachments
- Use HTML formatting
- Override SMTP settings per email

### `test_smtp_connection_tool` - Check Setup
Test your email settings before sending important emails.

## Getting Started

### 1. Install Required Software

```bash
# Install uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Restart your terminal or run:
source ~/.bashrc
```

### 2. Install Project Dependencies

```bash
cd email-mcp-server
uv sync
```

### 3. Test the Installation

```bash
# Test your email setup
uv run python test_email.py

# Run the server directly (for testing)
uv run main.py
```

### 4. Configure Claude Desktop or Cursor

Add this to your Claude Desktop configuration or Cursor file:
```json
{
  "mcpServers": {
      "mcp-server": {
          "command": "uv",
          "args": [
              "--directory",
              "path/to/the/app/email-mcp-server",
              "run",
              "main.py"
          ],
          "env": {
              "SMTP_HOST": "",
              "SMTP_PORT": "",
              "SMTP_SECURE": "",
              "SMTP_USER": "",
              "SMTP_FROM": "",
              "SMTP_PASS": ""
          }
      }
  }
}
```

**Important**: Change the directory path to match your actual installation location.

### Simple Examples

**Send a basic email:**
```
"Send an email to john@company.com saying the meeting is tomorrow at 2 PM"
```

**Send with HTML formatting:**
```
"Send an HTML email to team@company.com with subject 'Weekly Update' and create a nice formatted message about this week's progress"
```

**Test your setup:**
```
"Test the email connection to make sure it's working"
```

### Advanced Examples

**Send to multiple people with attachments:**
```
"Send a custom email to the team about the project update. Send to team@company.com, CC manager@company.com, and attach the project report"
```

## Email Provider Setup

### For Gmail
```json
"env": {
    "SMTP_HOST": "smtp.gmail.com",
    "SMTP_PORT": "587",
    "SMTP_SECURE": "false",
    "SMTP_USER": "your-email@gmail.com",
    "SMTP_FROM": "your-email@gmail.com",
    "SMTP_PASS": "your-app-password"
}
```

**Gmail Setup Steps:**
1. Enable 2-Factor Authentication
2. Go to Google Account → Security → App passwords
3. Generate an app password for "Mail"
4. Use the 16-character app password

### For Outlook
```json
"env": {
    "SMTP_HOST": "smtp-mail.outlook.com",
    "SMTP_PORT": "587",
    "SMTP_SECURE": "false",
    "SMTP_USER": "your-email@outlook.com",
    "SMTP_FROM": "your-email@outlook.com",
    "SMTP_PASS": "your-password"
}
```

### For Other Providers
Replace the SMTP settings with your provider's details. Most providers use:
- Port 587 with SMTP_SECURE=false (STARTTLS)
- Port 465 with SMTP_SECURE=true (SSL)

## Configuration Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `SMTP_HOST` | Your email server | `smtp.gmail.com` |
| `SMTP_PORT` | Server port | `587` |
| `SMTP_SECURE` | Use SSL (true/false) | `false` |
| `SMTP_USER` | Your username | `user@gmail.com` |
| `SMTP_FROM` | Sender address | `noreply@company.com` |
| `SMTP_PASS` | Your password | `your-password` |

## Troubleshooting

### "Missing Configuration"
- Make sure all environment variables are set in the Claude Desktop config
- Check that the directory path is correct and absolute
- Restart Claude Desktop after making changes

### "Authentication Failed"
- For Gmail/Yahoo: Use app passwords, not regular passwords
- Enable 2-Factor Authentication first
- Double-check username and password

### "Connection Issues"
- Verify SMTP host and port are correct
- Check your internet connection
- Some networks block SMTP ports

### "Server Not Found"
- Make sure `uv` is installed and in your PATH
- Check that the directory path exists
- Verify the project dependencies are installed with `uv sync`

## Testing

```bash
# Test configuration and connection
uv run python test_email.py

# Send a real test email to yourself
uv run python test_email.py --send-real
```


## License

MIT License - Feel free to use and modify as needed.
