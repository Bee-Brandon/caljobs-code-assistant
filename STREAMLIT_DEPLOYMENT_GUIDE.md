# Deploying to Streamlit Community Cloud

## Overview
Streamlit Community Cloud is free and connects directly to your GitHub repo.
Once deployed, anyone with the URL can access your app from any device.

---

## Pre-Deployment Checklist

### 1. Verify your GitHub repo is up to date

Open your terminal in your project folder and run:
```bash
git remote -v
```
If it shows a GitHub URL, you're connected. If not:
```bash
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
```

Push your latest code:
```bash
git add .
git commit -m "Add PDF filler service and county form templates"
git push origin main
```

### 2. Make sure these files exist in your repo

```
your-project/
├── app.py                          # Main Streamlit app
├── requirements.txt                # Python dependencies
├── .gitignore                      # Excludes .env, __pycache__, etc.
├── templates/
│   └── county_forms/
│       ├── Attachment_V_WIOA_Applicant_Acknowledgement_Statements.pdf
│       ├── Attachment_IV_WIOA_Complaint_Resolutions__Participant_Acceptance_Form.pdf
│       └── code_of_conduct.pdf
├── app/
│   └── services/
│       ├── pdf_filler.py           # NEW — county form filler
│       └── ... (other services)
└── .streamlit/
    └── config.toml                 # Optional — theme/config
```

### 3. Update requirements.txt

Make sure ALL dependencies are listed. Here's what your app needs:
```
streamlit
anthropic
reportlab
Pillow
qrcode
pypdf
python-dotenv
```

If you're unsure what's installed, run this in your project folder:
```bash
pip freeze > requirements_full.txt
```
Then pick out only the packages your app actually imports.

**IMPORTANT:** Do NOT include `pywin32`, `pyautogui`, or any Windows-only 
packages — Streamlit Cloud runs Linux and they will fail.

### 4. Create .gitignore (if you don't have one)

Create a file called `.gitignore` in your project root:
```
.env
__pycache__/
*.pyc
.DS_Store
saved_sessions/
qr_codes/
```

**CRITICAL: Never push your .env file to GitHub.** It contains your API keys 
and email passwords. The .gitignore prevents this.

---

## Deployment Steps

### Step 1: Go to Streamlit Cloud

1. Open https://share.streamlit.io
2. Sign in with your GitHub account
3. Click "New app"

### Step 2: Configure the app

Fill in:
- **Repository:** Select your repo (e.g., Bee-Brandon/orientation-intake)
- **Branch:** main
- **Main file path:** app.py

### Step 3: Add your secrets (environment variables)

Click "Advanced settings" before deploying.

In the **Secrets** box, paste your environment variables in TOML format:
```toml
ANTHROPIC_API_KEY = "your_api_key_here"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = "587"
SMTP_USERNAME = "your_email@gmail.com"
SMTP_PASSWORD = "your_gmail_app_password"
DEFAULT_RECIPIENTS = "staff1@org.com,staff2@org.com"
```

**This replaces your .env file.** Streamlit Cloud doesn't use .env — it uses 
this secrets system instead.

### Step 4: Update your config.py to read from Streamlit secrets

Your config.py currently reads from .env using `os.getenv()`. For Streamlit 
Cloud, you need to ALSO check `st.secrets`. Here's the pattern:

```python
import os
import streamlit as st

def get_secret(key, default=""):
    """Read from Streamlit secrets first, fall back to .env / os.getenv."""
    try:
        return st.secrets[key]
    except (KeyError, FileNotFoundError):
        return os.getenv(key, default)
```

Then replace all `os.getenv("ANTHROPIC_API_KEY")` calls with 
`get_secret("ANTHROPIC_API_KEY")`.

Tell Claude Code:
"Update config.py to add a get_secret() helper function that tries 
st.secrets first and falls back to os.getenv(). Then replace all 
os.getenv() calls in config.py with get_secret(). This makes the app 
work both locally (with .env) and on Streamlit Cloud (with secrets)."

### Step 5: Deploy

Click "Deploy!" — Streamlit will:
1. Clone your repo
2. Install requirements.txt
3. Run your app.py
4. Give you a public URL like: https://your-app-name.streamlit.app

---

## After Deployment

### Your app URL
You'll get a URL like:
```
https://orientation-intake.streamlit.app
```
This is the link staff and participants use. Works on any device with a browser.

### QR Code Update
Your QR code generator currently points to localhost. After deployment, 
update the base URL in your config to point to your Streamlit Cloud URL.

Tell Claude Code:
"Update the QR code generator to use the deployed URL instead of localhost. 
The base URL should be configurable via an environment variable called 
APP_BASE_URL, defaulting to http://localhost:8501 for local development."

Then add to your Streamlit Cloud secrets:
```toml
APP_BASE_URL = "https://your-app-name.streamlit.app"
```

### Updating the app
Any time you push to your main branch on GitHub, Streamlit Cloud 
automatically redeploys. Just:
```bash
git add .
git commit -m "description of changes"
git push origin main
```
Wait ~60 seconds and the live app updates.

### Monitoring
Streamlit Cloud shows logs in the dashboard. If the app crashes, check 
the logs — it's usually a missing package in requirements.txt or a 
secret that wasn't configured.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| "ModuleNotFoundError" | Add the missing package to requirements.txt and push |
| App won't start | Check logs — likely a missing secret or import error |
| Email not sending | Verify SMTP secrets are set correctly in Streamlit Cloud |
| "No module named 'anthropic'" | Add `anthropic` to requirements.txt |
| Slow first load | Normal — free tier cold-starts take 30-60 seconds |
| App sleeps after inactivity | Free tier sleeps after ~7 days of no traffic. Wakes on next visit. |
