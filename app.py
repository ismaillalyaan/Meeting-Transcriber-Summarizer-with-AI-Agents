import streamlit as st
import os
import subprocess
from pathlib import Path
from project import Crew
import concurrent.futures

# Import your agents and tasks
from project import (
    SummarizerAgent,
    ActionItemAgent,
    EmailAgent,
    MailerAgent,
    SummarizationTask,
    ActionItemsTask,
    EmailDraftTask,
    MailerTask,
    pipe
)

# --- Streamlit UI Setup ---
st.set_page_config(page_title="Meeting Assistant", layout="wide")
st.title("📋 AI Meeting Assistant")

with st.sidebar:
    st.header("⚙️ Options")
    source = st.radio("Audio Source", ["YouTube URL", "Upload File"])
    run_summarize = st.checkbox("Summarize Transcript", True)
    run_actions = st.checkbox("Extract Action Items", True)
    run_email = st.checkbox("Draft Follow-up Email", True)
    run_send = st.checkbox("Send Email Automatically", False)

    st.markdown("---")
    st.subheader("SMTP Settings")
    smtp_email = st.text_input("Sender Email", os.getenv("SMTP_EMAIL", ""))
    smtp_receiver = st.text_input("Receiver Email", os.getenv("SMTP_RECEIVER", ""))
    smtp_password = st.text_input("Password", type="password")

# --- File Input ---
audio_file_path = st.session_state.get("audio_file_path", None)

if source == "YouTube URL":
    yt_url = st.text_input("Enter YouTube URL")
    if yt_url and st.button("Download Audio"):
        out_folder = "my_audio_folder"
        os.makedirs(out_folder, exist_ok=True)
        command = [
            "yt-dlp", "-f", "bestaudio/best",
            "--extract-audio", "--audio-format", "mp3",
            "-o", f"{out_folder}/%(title)s.%(ext)s", yt_url
        ]
        subprocess.run(command)
        audio_file_path = next(Path(out_folder).glob("*.mp3"))
        st.session_state["audio_file_path"] = audio_file_path
        st.success(f"Downloaded: {audio_file_path.name}")

else:
    uploaded_file = st.file_uploader("Upload an audio file", type=["mp3", "wav", "m4a"])
    if uploaded_file:
        out_folder = "uploads"
        os.makedirs(out_folder, exist_ok=True)
        audio_file_path = Path(out_folder) / uploaded_file.name
        with open(audio_file_path, "wb") as f:
            f.write(uploaded_file.read())
        st.session_state["audio_file_path"] = audio_file_path
        st.success(f"Uploaded: {audio_file_path.name}")


# --- Helper for transcription ---
def run_transcription(audio_file_path):
    result = pipe(str(audio_file_path))
    return result["text"]


# --- Run Pipeline ---
if audio_file_path and st.button("Run Processing", key="process_btn"):
    with st.spinner("🔎 Transcribing audio..."):
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(run_transcription, audio_file_path)
            transcript = future.result()

    st.subheader("Transcript")
    st.write(transcript[:1000] + "...")  # Preview first 1000 chars

    # Prepare agents & tasks
    agents = []
    tasks = []
    if run_summarize:
        agents.append(SummarizerAgent)
        tasks.append(SummarizationTask)
    if run_actions:
        agents.append(ActionItemAgent)
        tasks.append(ActionItemsTask)
    if run_email:
        agents.append(EmailAgent)
        tasks.append(EmailDraftTask)
    if run_send:
        os.environ["SMTP_EMAIL"] = smtp_email
        os.environ["SMTP_RECEIVER"] = smtp_receiver
        os.environ["SMTP_PASSWORD"] = smtp_password
        agents.append(MailerAgent)
        tasks.append(MailerTask)

    # Run Crew pipeline
    crew = Crew(agents=agents, tasks=tasks, verbose=True)
    results = crew.kickoff(inputs={"transcript": transcript})

    # Display results
    for i, task_output in enumerate(results.tasks_output, start=1):
        st.subheader(f"Step {i}:")
        st.write(task_output)
