# IAM Knowledge Hub

A lightweight, free IAM news dashboard hosted on GitHub Pages.

## What it does

- Displays selected Identity and Access Management news in a card-based dashboard.
- Searches public news results every Monday.
- Removes duplicate headlines.
- Classifies articles into IAM categories.
- Ranks articles using keyword-based relevance.
- Creates a weekly archive.
- Does not require a paid AI API.

## First-time setup

1. Upload all files and folders from this package to the root of your GitHub repository.
2. In GitHub, open **Settings → Pages**.
3. Under **Build and deployment**, choose:
   - **Source:** Deploy from a branch
   - **Branch:** `main`
   - **Folder:** `/ (root)`
4. Click **Save**.
5. Open **Actions → Update IAM news → Run workflow** to perform the first live update.
6. Wait a few minutes, then reopen the dashboard.

Your public address will normally be:

`https://YOUR-USERNAME.github.io/YOUR-REPOSITORY-NAME/`

For the repository supplied in the conversation, it should be:

`https://valeriatt1.github.io/iam-knowlegde-hub/`

## Important limitation

The weekly collector is automatic, but it is not generative AI. It uses public Google News RSS search results and a transparent keyword-based relevance model. This avoids paid API usage. Search results and RSS behaviour can change over time.

## Schedule

The workflow runs every Monday at 07:15 UTC. You can also run it manually from the **Actions** tab.

## Safety

The site contains only public information. Do not add confidential company, client or personal information to a public repository.
