# CalJOBS Code Assistant

AI-powered code lookup tool for CalJOBS activity codes and NAICS industry codes.

## Features
- 326 CalJOBS activity codes across 15 categories
- 2,950+ NAICS industry codes with hierarchical browsing
- AI assistant for natural language code selection
- Quick actions for common tasks (supportive services, employer contact, etc.)
- Search and browse functionality with fuzzy matching

## Deployment
This app is deployed on Streamlit Cloud.

## Setup
1. Add your Anthropic API key in Streamlit Cloud secrets
2. Key name: `ANTHROPIC_API_KEY`
3. Get your key from: https://console.anthropic.com

### Streamlit Cloud Secrets
In your Streamlit Cloud dashboard, add this to your app secrets:
```toml
ANTHROPIC_API_KEY = "sk-ant-your-key-here"
```

## Usage
- **AI Assistant** tab: Describe what you're doing in plain English and get code recommendations
- **Quick Actions** sidebar: One-click access to common codes (workshop incentives, transportation, etc.)
- **Search** tab: Find specific CalJOBS or NAICS codes by keyword
- **Browse** tab: Explore all codes by category or NAICS sector

## Local Development
```bash
pip install -r requirements.txt
streamlit run web_app.py
```
