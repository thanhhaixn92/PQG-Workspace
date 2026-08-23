# n8n Automation Sidecar

This directory contains the infrastructure configuration for running n8n locally as part of DIRAP Local Workbench.

## Setup Instructions

1. Generate a secure encryption key for n8n.
2. In the `infra/n8n/` directory, create a `.env` file (which is git-ignored) and add:
   ```env
   N8N_ENCRYPTION_KEY=your_secure_random_string_here
   HERMES_N8N_WEBHOOK_SECRET=your_secure_webhook_secret_here
   ```
3. Start the container:
   ```bash
   docker-compose up -d
   ```
4. Access the n8n UI at `http://127.0.0.1:5678`.

> [!WARNING]
> Never commit your `.env` or `N8N_ENCRYPTION_KEY` to version control. Doing so compromises the encryption of your stored n8n credentials.

## Sample Workflow

You can import `Sample_Webhook_Echo.json` into your n8n workspace to test the backend integration. This workflow validates the `X-Hermes-Secret` header to ensure only authorized local requests are processed.
