"""
Minimal Streamlit UI for the Multi-Source Candidate Data Transformer.

This is a thin view over the same engine the CLI uses (src/pipeline.py) — no
business logic lives here. Upload sources, pick/edit a config, run, see the
canonical profiles.

Run with:
    pip install -r requirements.txt
    streamlit run app.py
"""

import json
import os
import tempfile

import streamlit as st

from src.pipeline import run


st.set_page_config(page_title="Candidate Data Transformer", page_icon="🧩", layout="wide")

st.title("🧩 Multi-Source Candidate Data Transformer")
st.caption(
    "Fuse messy candidate data from many sources into one clean, canonical "
    "profile — with provenance and confidence. Thin UI over the same engine the CLI uses."
)


def _save_upload(uploaded_file) -> str | None:
    """Persist a Streamlit UploadedFile to a temp path and return it."""
    if uploaded_file is None:
        return None
    suffix = os.path.splitext(uploaded_file.name)[1]
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(uploaded_file.getvalue())
    tmp.flush()
    tmp.close()
    return tmp.name


# ── Sidebar: sources & config ─────────────────────────────────────────────────
with st.sidebar:
    st.header("1 · Sources")
    st.markdown("**Structured**")
    csv_file = st.file_uploader("Recruiter CSV", type=["csv"])
    ats_file = st.file_uploader("ATS JSON", type=["json"])

    st.markdown("**Unstructured**")
    notes_file = st.file_uploader("Recruiter notes (.txt)", type=["txt"])
    github_input = st.text_input(
        "GitHub usernames / URLs",
        placeholder="e.g. torvalds, octocat",
        help="Comma-separated. Hits the public GitHub API live.",
    )

    st.divider()
    st.header("2 · Output config")
    config_choice = st.radio(
        "Choose a config",
        ["Default (full canonical schema)", "Custom (reshaped output)", "Paste your own"],
        index=0,
    )


def _load_config_file(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


# Resolve config to a dict + a temp path the pipeline can read
config_dict: dict = {}
if config_choice.startswith("Default"):
    config_dict = _load_config_file("configs/default.json")
elif config_choice.startswith("Custom"):
    config_dict = _load_config_file("configs/custom.json")
else:
    pasted = st.sidebar.text_area(
        "Paste config JSON",
        value=json.dumps(_load_config_file("configs/custom.json"), indent=2),
        height=300,
    )
    try:
        config_dict = json.loads(pasted) if pasted.strip() else {}
    except json.JSONDecodeError as e:
        st.sidebar.error(f"Invalid JSON: {e}")
        config_dict = None

with st.sidebar:
    if config_dict is not None:
        with st.expander("Active config"):
            st.json(config_dict)

run_clicked = st.sidebar.button("▶ Run pipeline", type="primary", use_container_width=True)


# ── Main: run & show results ──────────────────────────────────────────────────
if run_clicked:
    github_urls = [g.strip() for g in github_input.split(",") if g.strip()] if github_input else None

    if not any([csv_file, ats_file, notes_file, github_urls]):
        st.warning("Provide at least one source in the sidebar.")
        st.stop()

    if config_dict is None:
        st.error("Fix the config JSON before running.")
        st.stop()

    # Persist uploads + config to temp files (pipeline reads paths)
    csv_path = _save_upload(csv_file)
    ats_path = _save_upload(ats_file)
    notes_path = _save_upload(notes_file)

    config_path = None
    if config_dict:
        cfg_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w")
        json.dump(config_dict, cfg_tmp)
        cfg_tmp.flush()
        cfg_tmp.close()
        config_path = cfg_tmp.name

    with st.spinner("Running ingest → normalize → merge → project → validate…"):
        try:
            profiles = run(
                csv_path=csv_path,
                ats_json_path=ats_path,
                github_urls=github_urls,
                notes_paths=[notes_path] if notes_path else None,
                config_path=config_path,
            )
        except Exception as e:
            st.error(f"Pipeline error: {e}")
            st.stop()

    if not profiles:
        st.warning("No profiles produced — sources may be empty or unparseable.")
        st.stop()

    st.success(f"Produced {len(profiles)} canonical profile(s).")

    # Summary table (best-effort across default & custom shapes)
    rows = []
    for p in profiles:
        rows.append({
            "name": p.get("full_name"),
            "email": (p.get("emails") or [p.get("primary_email")])[0]
            if isinstance(p.get("emails"), list) else p.get("primary_email"),
            "confidence": p.get("overall_confidence"),
            "skills": len(p.get("skills", [])) if isinstance(p.get("skills"), list) else None,
        })
    st.subheader("Summary")
    st.dataframe(rows, use_container_width=True)

    st.subheader("Profiles")
    for i, p in enumerate(profiles):
        label = p.get("full_name") or p.get("candidate_id") or f"Profile {i + 1}"
        with st.expander(f"📇 {label}", expanded=(len(profiles) == 1)):
            st.json(p)

    st.download_button(
        "⬇ Download JSON",
        data=json.dumps(profiles, indent=2, ensure_ascii=False),
        file_name="profiles.json",
        mime="application/json",
    )
else:
    st.info("⬅ Add at least one source and a config in the sidebar, then click **Run pipeline**.")
    st.markdown(
        "**Try the bundled samples** (from the repo root):\n"
        "- `samples/candidates.csv` — Recruiter CSV\n"
        "- `samples/ats_data.json` — ATS JSON\n"
        "- `samples/recruiter_notes.txt` — Recruiter notes\n\n"
        "Or just type a GitHub username like `torvalds`."
    )
