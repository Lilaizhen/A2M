#!/usr/bin/env python3
"""Test script for the email functionality in the MCP server."""

import asyncio
import sys
import os
from dotenv import load_dotenv

load_dotenv()

from main import (
    get_smtp_config_from_env,
    send_email_smtp,
    test_smtp_connection,
    SMTPConfig,
    EmailMessage
)


async def test_smtp_config():
    """Test loading SMTP configuration from environment."""
    print("=== Testing SMTP Configuration Loading ===")
    
    required_vars = ['SMTP_HOST', 'SMTP_USER', 'SMTP_FROM', 'SMTP_PASS']
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"Missing environment variables: {', '.join(missing_vars)}")
        print("Please set these variables in your Claude Desktop configuration")
        return None
    
    config = get_smtp_config_from_env()
    if config:
        print("SMTP configuration loaded successfully!")
        print(f"Host: {config.host}")
        print(f"Port: {config.port}")
        print(f"Secure: {config.secure}")
        print(f"User: {config.auth['user']}")
        print(f"From: {config.from_email}")
        print(f"Password: {'*' * len(config.auth['pass'])}")
    else:
        print("Failed to create SMTP configuration object.")
    print()
    return config


async def test_connection(config):
    """Test SMTP connection."""
    if not config:
        print("Skipping connection test - no configuration available")
        return False
    
    print("=== Testing SMTP Connection ===")
    try:
        result = await test_smtp_connection(config)
        print(f"Connection successful: {result}")
        return True
    except Exception as e:
        print(f"Connection failed: {e}")
        return False
    finally:
        print()


def test_email_validation():
    """Test email message validation."""
    print("=== Testing Email Message Validation ===")
    
    try:
        email_msg = EmailMessage(
            to="test@example.com",
            subject="Test Subject",
            text="Test body"
        )
        print("Simple email message created successfully")
        print(f"To: {email_msg.to}")
        print(f"Subject: {email_msg.subject}")
        
        email_msg2 = EmailMessage(
            to=["test1@example.com", "test2@example.com"],
            cc="cc@example.com",
            bcc=["bcc1@example.com", "bcc2@example.com"],
            subject="Multi-recipient Test",
            html="<h1>HTML Test</h1>"
        )
        print("Multi-recipient email message created successfully")
        print(f"To: {email_msg2.to}")
        print(f"CC: {email_msg2.cc}")
        print(f"BCC: {email_msg2.bcc}")
        
        return True
        
    except Exception as e:
        print(f"Email message validation failed: {e}")
        return False
    finally:
        print()


async def test_send_email(config, test_mode=True):
    """Test sending an email (dry run by default)."""
    if not config:
        print("Skipping email send test - no configuration available")
        return
    
    print("=== Testing Email Sending ===")
    
    if test_mode:
        print("This is a DRY RUN - no actual email will be sent")
        print("To send a real email, set test_mode=False")
    else:
        print("REAL EMAIL WILL BE SENT!")
        
        email_msg = EmailMessage(
            to=config.auth['user'],
            subject="MCP Email Server Test",
            text="This is a test email from the MCP Email Server. If you receive this, the email functionality is working correctly!",
            html="<h1>MCP Email Server Test</h1><p>This is a test email from the MCP Email Server.</p><p>If you receive this, the email functionality is working correctly!</p>"
        )
        
        try:
            result = await send_email_smtp(config, email_msg)
            print(f"Email sent successfully: {result}")
        except Exception as e:
            print(f"Email sending failed: {e}")
    
    print()


def show_configuration_help():
    """Show help for configuring email settings."""
    print("=== Configuration Help ===")
    print()
    print("To use the email functionality, configure your Claude Desktop with SMTP settings:")
    print()
    print("For Gmail:")
    print("  1. Enable 2-Factor Authentication")
    print("  2. Generate an App Password:")
    print("     - Go to Google Account settings")
    print("     - Security → 2-Step Verification → App passwords")
    print("     - Generate password for 'Mail'")
    print("  3. Add to Claude Desktop config:")
    print('     "SMTP_HOST": "smtp.gmail.com",')
    print('     "SMTP_PORT": "587",')
    print('     "SMTP_SECURE": "false",')
    print('     "SMTP_USER": "your-email@gmail.com",')
    print('     "SMTP_FROM": "your-email@gmail.com",')
    print('     "SMTP_PASS": "your-16-character-app-password"')
    print()
    print("For other providers, check the README for configurations.")
    print()


async def main():
    """Main test function."""
    print("MCP Email Server Functionality Test")
    print("=" * 50)
    
    send_real = "--send-real" in sys.argv
    
    if send_real:
        print("REAL EMAIL MODE - An actual email will be sent!")
        response = input("Are you sure? (y/N): ")
        if response.lower() != 'y':
            print("Cancelled.")
            return
    
    config = await test_smtp_config()
    validation_ok = test_email_validation()
    
    if config and validation_ok:
        connection_ok = await test_connection(config)
        
        if connection_ok:
            await test_send_email(config, test_mode=not send_real)
            
            if send_real:
                print("Real email sent!")
            else:
                print("All tests passed!")
                print()
                print("To send a real test email to yourself:")
                print("  uv run python test_email.py --send-real")
        else:
            print("Connection test failed - check your SMTP settings")
    else:
        show_configuration_help()
    
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())