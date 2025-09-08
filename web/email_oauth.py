"""
Microsoft Graph API Email Integration for Office 365
Uses OAuth2 for authentication instead of SMTP
"""

import requests
import json
import base64
from typing import Optional, Dict, Any, List
from msal import ConfidentialClientApplication

class MicrosoftGraphMailer:
    """Send emails using Microsoft Graph API with OAuth2"""
    
    def __init__(self, tenant_id: str, client_id: str, client_secret: str):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.token = None
        self.graph_url = "https://graph.microsoft.com/v1.0"
        
        # Initialize MSAL app
        self.app = ConfidentialClientApplication(
            client_id=self.client_id,
            client_credential=self.client_secret,
            authority=f"https://login.microsoftonline.com/{self.tenant_id}"
        )
        
    def get_access_token(self) -> str:
        """Get OAuth2 access token using MSAL"""
        # Try to get token from cache first
        result = self.app.acquire_token_silent(
            scopes=["https://graph.microsoft.com/.default"],
            account=None
        )
        
        if not result:
            # If not in cache, get new token
            result = self.app.acquire_token_for_client(
                scopes=["https://graph.microsoft.com/.default"]
            )
        
        if "access_token" in result:
            self.token = result['access_token']
            return self.token
        else:
            error_msg = result.get("error_description", "Unknown error getting token")
            raise Exception(f"Failed to get token: {error_msg}")
    
    def send_mail(self, from_address: str, to_address: str, subject: str, 
                  body_html: str, body_text: str = None, attachments: list = None):
        """Send email using Microsoft Graph API"""
        
        if not self.token:
            self.get_access_token()
        
        # Prepare the message
        message = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": "HTML",
                    "content": body_html
                },
                "toRecipients": [
                    {
                        "emailAddress": {
                            "address": to_address
                        }
                    }
                ]
            },
            "saveToSentItems": "true"
        }
        
        # Add attachments if provided
        if attachments:
            message["message"]["attachments"] = attachments
        
        # Send the email from the shared mailbox
        url = f"{self.graph_url}/users/{from_address}/sendMail"
        
        headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json'
        }
        
        response = requests.post(url, headers=headers, json=message)
        
        if response.status_code == 202:
            return {"status": "success", "message": "Email sent successfully"}
        else:
            raise Exception(f"Failed to send email: {response.text}")

# Configuration for OAuth2
import os

GRAPH_CONFIG = {
    # These will be set via environment variables in Azure
    "TENANT_ID": os.getenv('AZURE_TENANT_ID', 'your-tenant-id'),
    "CLIENT_ID": os.getenv('AZURE_CLIENT_ID', 'your-client-id'),
    "CLIENT_SECRET": os.getenv('AZURE_CLIENT_SECRET', 'your-client-secret'),
    "SHARED_MAILBOX": os.getenv('SHARED_MAILBOX', 'returns@uptimeops.net')
}

def send_email_oauth(recipient: str, subject: str, body_html: str, body_text: str = None, attachments: list = None):
    """Helper function to send email using OAuth2"""
    try:
        mailer = MicrosoftGraphMailer(
            GRAPH_CONFIG['TENANT_ID'],
            GRAPH_CONFIG['CLIENT_ID'],
            GRAPH_CONFIG['CLIENT_SECRET']
        )
        
        return mailer.send_mail(
            from_address=GRAPH_CONFIG['SHARED_MAILBOX'],
            to_address=recipient,
            subject=subject,
            body_html=body_html,
            body_text=body_text,
            attachments=attachments
        )
    except Exception as e:
        return {"status": "error", "message": str(e)}