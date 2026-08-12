"""Streamlit dashboard for the Podcast Generator system.

Run with:
    cd podcast-system/frontend
    pip install -r requirements.txt
    streamlit run app.py
"""

import time
from datetime import datetime, timezone

import requests
import streamlit as st

# ── Constants ─────────────────────────────────────────────────────────────────

import os

# API_BASE_URL: where the Streamlit *server* sends requests (inside Docker: http://nginx)
API_BASE = os.getenv("API_BASE_URL", "http://localhost")
# PUBLIC_BASE_URL: base URL embedded in links that the *user's browser* opens
PUBLIC_BASE = os.getenv("PUBLIC_BASE_URL", API_BASE)

POLL_INTERVAL_SECS = 3

ACTIVE_STATUSES = {"PENDING", "CRAWLING", "GENERATING"}
TERMINAL_STATUSES = {"DONE", "FAILED"}

STATUS_CONFIG: dict[str, dict] = {
    "PENDING": {
        "icon": "⏳",
        "label": "Pending",
        "color": "#6c757d",
        "progress": 0.05,
    },
    "CRAWLING": {
        "icon": "🕷️",
        "label": "Crawling web sources",
        "color": "#0d6efd",
        "progress": 0.40,
    },
    "GENERATING": {
        "icon": "⚙️",
        "label": "Generating audio",
        "color": "#e67e22",
        "progress": 0.75,
    },
    "DONE": {
        "icon": "✅",
        "label": "Ready",
        "color": "#27ae60",
        "progress": 1.0,
    },
    "FAILED": {
        "icon": "❌",
        "label": "Failed",
        "color": "#e74c3c",
        "progress": 1.0,
    },
}

PIPELINE_STEPS = ["Pending", "Crawling", "Generating", "Done"]
PIPELINE_STATUS_MAP = {
    "PENDING": 0,
    "CRAWLING": 1,
    "GENERATING": 2,
    "DONE": 3,
    "FAILED": -1,
}

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Podcast Generator",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    .block-container { padding-top: 1.8rem; padding-bottom: 2rem; }
    .stForm { background: #f8f9fa; border-radius: 12px; padding: 1.5rem; }
    .podcast-card { margin-bottom: 1rem; }
    div[data-testid="stHorizontalBlock"] { align-items: center; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Helpers ───────────────────────────────────────────────────────────────────


def _time_ago(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        secs = int((datetime.now(timezone.utc) - dt).total_seconds())
        if secs < 60:
            return f"{secs}s ago"
        if secs < 3600:
            return f"{secs // 60}m ago"
        return f"{secs // 3600}h ago"
    except Exception:
        return "—"


def _status_badge(status: str) -> str:
    cfg = STATUS_CONFIG.get(status, STATUS_CONFIG["PENDING"])
    return (
        f'<span style="'
        f"background:{cfg['color']};color:#fff;"
        f"padding:4px 13px;border-radius:20px;"
        f'font-size:0.82rem;font-weight:600;white-space:nowrap;">'
        f"{cfg['icon']} {cfg['label']}</span>"
    )


def _pipeline_indicator(status: str) -> str:
    step = PIPELINE_STATUS_MAP.get(status, 0)
    parts = []
    for i, name in enumerate(PIPELINE_STEPS):
        if status == "FAILED":
            color = "#e74c3c" if i == 0 else "#dee2e6"
            dot = "●" if i == 0 else "○"
        elif i < step:
            color = "#27ae60"
            dot = "●"
        elif i == step:
            color = STATUS_CONFIG.get(status, {}).get("color", "#6c757d")
            dot = "●"
        else:
            color = "#dee2e6"
            dot = "○"
        parts.append(
            f'<span style="color:{color};font-size:0.78rem;">{dot} {name}</span>'
        )
    connector = ' <span style="color:#dee2e6;"> › </span> '
    return connector.join(parts)


@st.cache_data(show_spinner=False)
def _fetch_audio(pod_id: str) -> bytes | None:
    """Fetch audio from the internal API (API_BASE) and cache by podcast ID."""
    path = f"/audio/{pod_id}.mp3"
    try:
        resp = requests.get(f"{API_BASE}{path}", timeout=30)
        resp.raise_for_status()
        return resp.content
    except Exception:
        return None


def _api_post(topic: str, duration_hint: str) -> dict:
    resp = requests.post(
        f"{API_BASE}/podcasts",
        json={"topic": topic, "durationHint": duration_hint},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def _api_get_status(podcast_id: str) -> dict:
    resp = requests.get(f"{API_BASE}/podcasts/{podcast_id}", timeout=10)
    resp.raise_for_status()
    return resp.json()


def _audio_url(pod: dict) -> str:
    """URL for the user's browser (uses PUBLIC_BASE, not internal API_BASE)."""
    path = pod.get("audioUrl") or f"/audio/{pod['podcastId']}.mp3"
    return f"{PUBLIC_BASE}{path}"


# ── Session state ─────────────────────────────────────────────────────────────

if "podcasts" not in st.session_state:
    st.session_state.podcasts: dict[str, dict] = {}

# ── Refresh active jobs before rendering ──────────────────────────────────────

has_active = False
for pid in list(st.session_state.podcasts):
    pod = st.session_state.podcasts[pid]
    if pod["status"] in ACTIVE_STATUSES:
        try:
            st.session_state.podcasts[pid].update(_api_get_status(pid))
        except Exception:
            pass
        if st.session_state.podcasts[pid]["status"] in ACTIVE_STATUSES:
            has_active = True

# ── Header ────────────────────────────────────────────────────────────────────

header_col, metric_col = st.columns([4, 1])

with header_col:
    st.title("🎙️ Podcast Generator")
    st.markdown(
        "Enter a topic to generate a spoken podcast episode. "
        "Track its progress live — a **Listen** button appears once it's ready."
    )

with metric_col:
    total = len(st.session_state.podcasts)
    done = sum(1 for p in st.session_state.podcasts.values() if p["status"] == "DONE")
    active = sum(1 for p in st.session_state.podcasts.values() if p["status"] in ACTIVE_STATUSES)
    if total:
        st.metric("Total", total)
        st.metric("Ready", done)
        if active:
            st.metric("In Progress", active)

st.divider()

# ── Generate form ─────────────────────────────────────────────────────────────

with st.form("generate", clear_on_submit=True):
    topic = st.text_input(
        "What should the podcast be about?",
        placeholder="e.g. The history of the internet, How black holes form, The rise of hip-hop…",
        max_chars=500,
    )
    duration = st.radio(
        "Episode length",
        options=["short", "medium", "long"],
        index=1,
        horizontal=True,
        help="Short ≈ 2-3 min  ·  Medium ≈ 5-7 min  ·  Long ≈ 10-12 min",
    )
    submitted = st.form_submit_button("🚀  Generate Podcast", type="primary")

if submitted:
    if not topic.strip():
        st.warning("Please enter a topic before generating.")
    else:
        with st.spinner("Submitting to the pipeline…"):
            try:
                result = _api_post(topic.strip(), duration)
                pid = result["podcastId"]
                st.session_state.podcasts[pid] = {
                    "podcastId": pid,
                    "topic": topic.strip(),
                    "durationHint": duration,
                    "status": "PENDING",
                    "audioUrl": None,
                    "createdAt": datetime.now(timezone.utc).isoformat(),
                }
                st.success(f"Queued!  ID: `{pid}`")
                st.rerun()
            except requests.HTTPError as exc:
                st.error(
                    f"API returned {exc.response.status_code}: {exc.response.text}"
                )
            except Exception as exc:
                st.error(f"Could not reach the API at {API_BASE} — is the stack running?  ({exc})")

# ── Dashboard ─────────────────────────────────────────────────────────────────

st.divider()

if not st.session_state.podcasts:
    st.info("No podcasts yet — enter a topic above to get started.")
else:
    count = len(st.session_state.podcasts)
    st.subheader(f"My Podcasts  ({count})")

    for pod in reversed(list(st.session_state.podcasts.values())):
        status = pod["status"]
        cfg = STATUS_CONFIG.get(status, STATUS_CONFIG["PENDING"])

        with st.container(border=True):
            # ── Row 1: title + status badge ───────────────────────────────
            title_col, badge_col = st.columns([5, 2])

            with title_col:
                st.markdown(f"#### {pod['topic']}")
                st.caption(
                    f"ID `{pod['podcastId'][:8]}…`  ·  "
                    f"{pod['durationHint'].capitalize()}  ·  "
                    f"{_time_ago(pod.get('createdAt', ''))}"
                )

            with badge_col:
                st.markdown(_status_badge(status), unsafe_allow_html=True)

            # ── Row 2: pipeline indicator ─────────────────────────────────
            st.markdown(
                _pipeline_indicator(status),
                unsafe_allow_html=True,
            )

            # ── Row 3: progress / audio ───────────────────────────────────
            if status in ACTIVE_STATUSES:
                st.progress(
                    cfg["progress"],
                    text=f"{cfg['label']}…  This may take a minute.",
                )

            elif status == "DONE":
                url = _audio_url(pod)

                listen_col, spacer = st.columns([2, 5])
                with listen_col:
                    st.link_button(
                        "🎧  Listen in browser",
                        url,
                        use_container_width=True,
                        type="primary",
                    )

                audio_bytes = _fetch_audio(pod["podcastId"])
                if audio_bytes:
                    st.audio(audio_bytes, format="audio/mp3")
                else:
                    st.caption(f"Audio file: `{url}`")

            elif status == "FAILED":
                st.error(
                    "Generation failed — the pipeline could not produce a valid script. "
                    "Try rephrasing the topic or choosing a different length."
                )

# ── Auto-refresh while jobs are active ────────────────────────────────────────

if has_active:
    time.sleep(POLL_INTERVAL_SECS)
    st.rerun()
