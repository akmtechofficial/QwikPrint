import os
import smtplib
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

# Load .env.local
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env.local"))

def _send_email_task(to_email: str, subject: str, html_content: str):
    smtp_user = (os.getenv("EMAIL") or os.getenv("SMTP_EMAIL") or "").strip()
    smtp_pass = (os.getenv("APP_PASSWORD") or os.getenv("SMTP_PASSWORD") or "").strip()

    if not smtp_user or not smtp_pass:
        print(f"[Email Warning] SMTP credentials missing. Could not send email '{subject}' to {to_email}.")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"QwikPrint SaaS <{smtp_user}>"
    msg["To"] = to_email

    part = MIMEText(html_content, "html")
    msg.attach(part)

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=12) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, [to_email], msg.as_string())
        print(f"[Email Success] Sent '{subject}' to {to_email}")
    except Exception as e:
        print(f"[Email Error] Failed to send email to {to_email}: {e}")

def send_async_email(to_email: str, subject: str, html_content: str):
    thread = threading.Thread(target=_send_email_task, args=(to_email, subject, html_content), daemon=True)
    thread.start()

def notify_new_user_registration(user_info: dict, shop_info: dict, client_ip: str, device_fp: str):
    admin_email = (os.getenv("ADMIN_EMAIL") or os.getenv("EMAIL") or "").strip()
    user_email = user_info.get("email", "")
    full_name = user_info.get("full_name", "Shop Owner")
    phone = user_info.get("phone", "N/A")
    shop_name = shop_info.get("name", "Print Shop")
    expires_at = shop_info.get("plan_expires_at", "7 Days")

    # 1. Admin Email HTML
    admin_subject = f"🚀 New QwikPrint Registration: {shop_name}"
    admin_html = f"""
    <div style="font-family: 'Segoe UI', Arial, sans-serif; background-color: #0f172a; color: #f8fafc; padding: 30px; border-radius: 12px; max-width: 600px; margin: 0 auto; border: 1px solid #334155;">
        <div style="text-align: center; border-bottom: 1px solid #334155; padding-bottom: 20px; margin-bottom: 20px;">
            <h1 style="color: #38bdf8; margin: 0; font-size: 24px;">🎉 New Shopkeeper Sign-Up!</h1>
            <p style="color: #94a3b8; font-size: 14px; margin-top: 5px;">A new shopkeeper just onboarded on QwikPrint.</p>
        </div>
        <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
            <tr><td style="padding: 10px; border-bottom: 1px solid #1e293b; color: #94a3b8; font-weight: 600;">Shop Name:</td><td style="padding: 10px; border-bottom: 1px solid #1e293b; color: #ffffff; font-weight: 700;">{shop_name}</td></tr>
            <tr><td style="padding: 10px; border-bottom: 1px solid #1e293b; color: #94a3b8; font-weight: 600;">Owner Name:</td><td style="padding: 10px; border-bottom: 1px solid #1e293b; color: #ffffff;">{full_name}</td></tr>
            <tr><td style="padding: 10px; border-bottom: 1px solid #1e293b; color: #94a3b8; font-weight: 600;">Email Address:</td><td style="padding: 10px; border-bottom: 1px solid #1e293b; color: #38bdf8;">{user_email}</td></tr>
            <tr><td style="padding: 10px; border-bottom: 1px solid #1e293b; color: #94a3b8; font-weight: 600;">Phone Number:</td><td style="padding: 10px; border-bottom: 1px solid #1e293b; color: #ffffff;">{phone}</td></tr>
            <tr><td style="padding: 10px; border-bottom: 1px solid #1e293b; color: #94a3b8; font-weight: 600;">Trial Period:</td><td style="padding: 10px; border-bottom: 1px solid #1e293b; color: #4ade80; font-weight: 700;">7-Day Free Trial (Expires: {expires_at})</td></tr>
            <tr><td style="padding: 10px; border-bottom: 1px solid #1e293b; color: #94a3b8; font-weight: 600;">Registration IP:</td><td style="padding: 10px; border-bottom: 1px solid #1e293b; color: #cbd5e1;">{client_ip}</td></tr>
            <tr><td style="padding: 10px; border-bottom: 1px solid #1e293b; color: #94a3b8; font-weight: 600;">Device FP:</td><td style="padding: 10px; border-bottom: 1px solid #1e293b; color: #cbd5e1; font-family: monospace;">{device_fp}</td></tr>
        </table>
        <div style="text-align: center; color: #64748b; font-size: 12px; margin-top: 20px;">
            QwikPrint SaaS System Notification • Automated Alert
        </div>
    </div>
    """
    send_async_email(admin_email, admin_subject, admin_html)

    # 2. Welcome User Email HTML
    if user_email:
        welcome_subject = f" Welcome to QwikPrint! Your 7-Day Free Trial is Active"
        welcome_html = f"""
        <div style="font-family: 'Segoe UI', Arial, sans-serif; background-color: #0f172a; color: #f8fafc; padding: 30px; border-radius: 12px; max-width: 600px; margin: 0 auto; border: 1px solid #334155;">
            <div style="text-align: center; border-bottom: 1px solid #334155; padding-bottom: 20px; margin-bottom: 20px;">
                <h1 style="color: #06b6d4; margin: 0; font-size: 26px;">Welcome to QwikPrint! 🚀</h1>
                <p style="color: #94a3b8; font-size: 15px; margin-top: 8px;">Hi {full_name}, your smart print counter dashboard is ready.</p>
            </div>
            <p style="font-size: 15px; line-height: 1.6; color: #cbd5e1;">
                Thank you for joining <strong>QwikPrint</strong>! Your shop <strong style="color: #ffffff;">{shop_name}</strong> has been registered with a <strong>7-Day Free Trial</strong>.
            </p>
            <div style="background: rgba(6, 182, 212, 0.1); border: 1px solid rgba(6, 182, 212, 0.3); border-radius: 10px; padding: 16px; margin: 20px 0;">
                <h3 style="margin: 0 0 10px; color: #38bdf8; font-size: 16px;">🔑 Account Summary</h3>
                <ul style="margin: 0; padding-left: 20px; color: #e2e8f0; font-size: 14px; line-height: 1.8;">
                    <li><strong>Shop Name:</strong> {shop_name}</li>
                    <li><strong>Owner Name:</strong> {full_name}</li>
                    <li><strong>Registered Email:</strong> {user_email}</li>
                    <li><strong>Trial Status:</strong> <span style="color: #4ade80; font-weight: bold;">Active (7 Days Free)</span></li>
                </ul>
            </div>
            <div style="text-align: center; margin: 25px 0;">
                <a href="http://localhost:8000/dashboard" style="background: linear-gradient(135deg, #0284c7, #2563eb); color: #ffffff; text-decoration: none; padding: 14px 28px; border-radius: 8px; font-weight: bold; font-size: 16px; display: inline-block;">
                    Open Shopkeeper Dashboard 📊
                </a>
            </div>
            <p style="font-size: 14px; color: #94a3b8; line-height: 1.5;">
                If you have any questions or need help setting up your print agent on your counter PC, feel free to reply directly to this email.
            </p>
            <div style="text-align: center; border-top: 1px solid #1e293b; padding-top: 16px; margin-top: 24px; color: #64748b; font-size: 12px;">
                © 2026 QwikPrint Automated Print Counter System. All rights reserved.
            </div>
        </div>
        """
        send_async_email(user_email, welcome_subject, welcome_html)
