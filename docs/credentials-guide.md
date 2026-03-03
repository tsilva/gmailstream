# Creating OAuth Credentials for gmailstream

gmailstream connects to your Gmail account using **OAuth 2.0**. This means you never hand your password to the tool — instead, Google issues a short-lived access token after you grant permission in a browser.

To make this work you need a **credentials.json** file from the Google Cloud Console. Follow these steps:

## 1. Create or open a Google Cloud project

1. Go to [https://console.cloud.google.com/](https://console.cloud.google.com/)
2. Click the project dropdown at the top, then **New Project**
3. Give it a name (e.g. `gmailstream`) and click **Create**

## 2. Enable the Gmail API

1. In the left sidebar, go to **APIs & Services → Library**
2. Search for **Gmail API**
3. Click it, then click **Enable**

## 3. Configure the OAuth consent screen

1. Go to **APIs & Services → OAuth consent screen**
2. Choose **External** (unless your account is part of a Google Workspace org, in which case **Internal** is simpler)
3. Fill in:
   - **App name**: anything (e.g. `gmailstream`)
   - **User support email**: your email
   - **Developer contact information**: your email
4. Click **Save and Continue** through the remaining screens (Scopes and Test users can be left at defaults)
5. On the **Test users** screen, add your own Gmail address as a test user
6. Click **Back to Dashboard**

## 4. Create OAuth client credentials

1. Go to **APIs & Services → Credentials**
2. Click **+ Create Credentials → OAuth client ID**
3. Application type: **Desktop app**
4. Name: anything (e.g. `gmailstream-desktop`)
5. Click **Create**

## 5. Download credentials.json

After creation, a dialog appears with your Client ID and Secret.

1. Click **Download JSON** (the download icon on the right)
2. Save the file somewhere accessible — you will provide this path to `gmailstream profiles init`

> **Keep this file private.** It contains your OAuth client secret. Do not commit it to version control.

## 6. Run profiles init

```bash
gmailstream profiles init my-profile
```

When prompted for the credentials path, enter the full path to the file you just downloaded. The tool will copy it into the profile directory and immediately open a browser for you to authorize access.
