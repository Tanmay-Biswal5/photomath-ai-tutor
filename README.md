# PhotoMath Tutor

A Streamlit math tutor that accepts text questions or photos of math problems, explains solutions step by step with Google Gemini, and can email a session summary through SMTP.

## Run locally

1. Create and activate a Python virtual environment.
2. Install dependencies with `pip install -r requirements.txt`.
3. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and add your Gemini API key. Add SMTP settings if you want email summaries.
4. Start the app with `streamlit run app.py`.

Never commit `.streamlit/secrets.toml`. For Streamlit Community Cloud, add the same settings in the app's Secrets configuration after deployment.

## Email summaries

Email summaries use SMTP. The sender account must permit SMTP sending, and the sender address must be authorized by the provider. Email support remains optional; chat works without SMTP settings.