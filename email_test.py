from email_utils import send_email

# Test values
subject = "🔍 Debug Email Test"
body = "<h1>This is a test email from GitHub Actions</h1>"
recipient = "your-real-email@example.com"

print("⚡ Starting test...")
send_email(subject, body, recipient, is_html=True)
print("✅ Script finished")
