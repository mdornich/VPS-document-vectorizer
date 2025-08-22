"""
Simple email sender using Gmail SMTP.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import json
import structlog

logger = structlog.get_logger()

class EmailSender:
    """Simple Gmail SMTP email sender."""
    
    def __init__(self):
        # Gmail SMTP configuration from environment
        import os
        self.smtp_host = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
        self.smtp_port = int(os.environ.get('SMTP_PORT', '587'))
        self.smtp_username = os.environ.get('SMTP_USERNAME', '')
        self.smtp_password = os.environ.get('SMTP_PASSWORD', '')
        self.from_email = os.environ.get('SMTP_FROM_EMAIL', self.smtp_username)
        self.to_email = os.environ.get('ALERT_EMAIL', 'admin@stablemischief.ai')
        
    def send_alert(self, subject: str, error_message: str, details: dict = None) -> bool:
        """
        Send an email alert.
        
        Args:
            subject: Email subject
            error_message: Main error message
            details: Additional details dictionary
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.from_email
            msg['To'] = self.to_email
            
            # Create HTML content
            html_content = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; }}
                    .alert-box {{ 
                        background: #f8f9fa; 
                        border: 2px solid #dc3545; 
                        border-radius: 5px; 
                        padding: 20px;
                        margin: 20px 0;
                    }}
                    .timestamp {{ color: #6c757d; }}
                    .error {{ color: #dc3545; font-weight: bold; }}
                    .details {{ 
                        background: white; 
                        border: 1px solid #dee2e6;
                        border-radius: 3px;
                        padding: 15px;
                        margin-top: 15px;
                    }}
                    pre {{ 
                        background: #f1f3f4;
                        padding: 10px;
                        border-radius: 3px;
                        overflow-x: auto;
                    }}
                </style>
            </head>
            <body>
                <div class="alert-box">
                    <h2>🚨 Document Vectorizer Alert</h2>
                    <p class="timestamp">Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                    <p class="error">Error: {error_message}</p>
                    
                    {f'''
                    <div class="details">
                        <h3>Details:</h3>
                        <pre>{json.dumps(details, indent=2) if details else "No additional details"}</pre>
                    </div>
                    ''' if details else ''}
                    
                    <p style="margin-top: 20px;">
                        <a href="http://localhost:5555" style="background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                            View Dashboard
                        </a>
                    </p>
                </div>
            </body>
            </html>
            """
            
            # Attach HTML
            part = MIMEText(html_content, 'html')
            msg.attach(part)
            
            # Connect and send
            logger.info(f"Connecting to Gmail SMTP server...")
            server = smtplib.SMTP(self.smtp_host, self.smtp_port)
            server.starttls()  # Enable TLS
            server.login(self.smtp_username, self.smtp_password)
            
            # Send email
            server.sendmail(self.from_email, self.to_email, msg.as_string())
            server.quit()
            
            logger.info(f"Email alert sent successfully to {self.to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False
    
    def send_test_alert(self) -> bool:
        """Send a test alert email."""
        return self.send_alert(
            subject=f"Test Alert - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            error_message="This is a test alert from the Document Vectorizer system",
            details={
                "status": "test",
                "message": "If you received this email, the alert system is working correctly!",
                "timestamp": datetime.now().isoformat(),
                "system": "Document Vectorizer",
                "environment": "production"
            }
        )

# Global instance
_email_sender = None

def get_email_sender() -> EmailSender:
    """Get or create the global email sender."""
    global _email_sender
    if _email_sender is None:
        _email_sender = EmailSender()
    return _email_sender

def send_error_alert(error_message: str, details: dict = None) -> bool:
    """
    Send an error alert email.
    
    Args:
        error_message: The error message
        details: Additional details
        
    Returns:
        True if sent successfully
    """
    sender = get_email_sender()
    subject = f"Document Vectorizer Error - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    return sender.send_alert(subject, error_message, details)

def test_email() -> bool:
    """Send a test email."""
    sender = get_email_sender()
    return sender.send_test_alert()