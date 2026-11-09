"""Streamlit entry point for the synthetic banking workbench."""
import json
from pathlib import Path
import sys
import tempfile
import time

import streamlit as st

# Works with either repository-root or indian_bank_suite/ entry points.
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from bankworkbench.engine import WorkEngine
from bankworkbench.fixtures import MODULES, PERSONAS, SCENARIOS
from bankworkbench.storage import WorkStore
from pfm.security import ConflictError, NotFoundError, ValidationError

st.set_page_config(page_title="Banking Workbench", page_icon="🏦", layout="wide")


def clear_identity():
    for key in list(st.session_state):
        if key not in ("workspace", "engine", "attempts"):
            del st.session_state[key]


def review(kind, draft, uid):
    st.session_state.pending = {
        "kind": kind, "draft": draft, "uid": uid,
        "expires": time.monotonic() + 300,
    }


def app():
    st.title("Banking Workbench")
    st.caption("Synthetic demonstration · Five banking workflows · No live bank connections")
    st.info("Use fictional information only. Each browser session has a separate temporary workspace. "
            "Refreshing or disconnecting can reset it. Download reports before leaving. "
            "Demo personas are public examples, not production authentication.")

    if "engine" not in st.session_state:
        workspace = tempfile.TemporaryDirectory(prefix="bank-streamlit-")
        store = WorkStore(Path(workspace.name) / "workbench.sqlite3")
        store.seed()
        st.session_state.workspace = workspace
        st.session_state.engine = WorkEngine(store)
    engine = st.session_state.engine
    now = time.monotonic()
    if "uid" in st.session_state:
        if now - st.session_state.last_seen >= 600 or now - st.session_state.signed_in >= 1800:
            clear_identity()
            st.warning("Session expired. Sign in again; your demo workspace is retained.")
        else:
            st.session_state.last_seen = now

    if "uid" not in st.session_state:
        st.subheader("Choose a demo persona")
        with st.expander("Demo sign-in details"):
            st.table([{"Username": uid, "Persona": p["name"], "Password": p["password"]}
                      for uid, p in PERSONAS.items()])
        with st.form("login"):
            uid = st.selectbox("Username", list(PERSONAS))
            password = st.text_input("Password", type="password")
            acknowledged = st.checkbox("I understand this is a fictional banking demonstration.")
            submitted = st.form_submit_button("Sign in", type="primary")
        if submitted:
            attempts = [t for t in st.session_state.get("attempts", []) if now - t < 60]
            st.session_state.attempts = attempts
            if len(attempts) >= 10:
                st.error("Too many attempts. Wait one minute.")
            elif not acknowledged:
                st.error("Please acknowledge the demo notice.")
            else:
                attempts.append(now)
                if not engine.store.authenticate_staff(uid, password):
                    st.error("Incorrect persona or password.")
                else:
                    engine.store.consent(uid, "workbench-privacy-1")
                    engine.store.audit(uid, "staff_login", {"interface": "streamlit"})
                    clear_identity()
                    st.session_state.uid = uid
                    st.session_state.last_seen = st.session_state.signed_in = now
                    st.rerun()
        return

    uid = st.session_state.uid
    board = engine.board(uid)
    with st.sidebar:
        st.subheader(board["profile"]["name"])
        st.caption("Switch personas here to complete an independent review in this workspace.")
        if st.button("Sign out / switch persona"):
            clear_identity()
            st.rerun()
        module = st.selectbox("Banking workflow", list(board["modules"]),
                              format_func=lambda m: MODULES[m]["name"], key="module")
        st.caption(MODULES[module]["subtitle"])
        st.caption("Analysis uses the original fixed demo clock: " + board["as_of"])

    if message := st.session_state.pop("notice", None):
        st.success(message)

    pending = st.session_state.get("pending")
    if pending:
        if pending["uid"] != uid or pending["expires"] <= now:
            del st.session_state.pending
            st.warning("Review expired. Review the proposed change again.")
        else:
            st.subheader("Review proposed change")
            st.json(pending["draft"])
            confirm, cancel = st.columns(2)
            if confirm.button("Confirm change", type="primary"):
                # The engine rechecks role, evidence, state and version at commit time.
                try:
                    ident = (engine.create(uid, pending["draft"]) if pending["kind"] == "create"
                             else engine.commit(uid, pending["draft"]))
                except (ValidationError, ConflictError, NotFoundError) as error:
                    del st.session_state.pending
                    st.error(str(error))
                else:
                    del st.session_state.pending
                    st.session_state.notice = "Change recorded for " + ident
                    st.rerun()
            if cancel.button("Cancel change"):
                del st.session_state.pending
                st.rerun()
            if "pending" in st.session_state:
                return

    st.header(MODULES[module]["name"])
    rows = [c for c in board["cases"] if c["module"] == module]
    a, b, c = st.columns(3)
    a.metric("Cases", len(rows))
    b.metric("Cases with blockers", sum(row["blockers"] > 0 for row in rows))
    c.metric("Awaiting review", sum(row["state"] == "PENDING_REVIEW" for row in rows))
    st.dataframe(rows, hide_index=True, width="stretch")

    if board["profile"]["role"] == "maker":
        with st.expander("Create a synthetic case"):
            with st.form("create_" + module):
                scenario = st.selectbox("Scenario", list(SCENARIOS[module]),
                                       format_func=lambda s: SCENARIOS[module][s])
                title = st.text_input("Case title", max_chars=80)
                reason = st.text_area("Intake rationale (at least 12 characters)", max_chars=1200)
                create = st.form_submit_button("Review new case")
            if create:
                draft = engine.validate_create(uid, {"module": module, "scenario": scenario,
                                                     "title": title, "reason": reason})
                review("create", draft, uid)
                st.rerun()

    if not rows:
        st.info("No cases in this workflow.")
        return
    lookup = {row["id"]: row for row in rows}
    ident = st.selectbox("Open case", list(lookup), key="case_" + module,
                        format_func=lambda i: i + " · " + lookup[i]["title"])
    detail = engine.detail(uid, ident)
    analysis = detail["analysis"]
    st.subheader(detail["case"]["title"])
    st.caption(f"{ident} · {detail['case']['state']} · Version {detail['case']['version']}")
    for col, metric in zip(st.columns(len(analysis["metrics"])), analysis["metrics"]):
        col.metric(metric["label"], metric["value"])
    findings, evidence, narrative, workflow, history = st.tabs(
        ["Findings", "Evidence", "Report", "Workflow", "History"])
    with findings:
        if not analysis["findings"]:
            st.success("No configured fixture inconsistencies detected.")
        for finding in analysis["findings"]:
            show = st.error if finding["severity"] == "blocker" else st.warning
            show(finding["title"] + ": " + finding["detail"])
            st.caption("Evidence: " + ", ".join(finding["evidence"]))
        st.caption(analysis["method"])
    with evidence:
        st.json(detail["facts"])
        if analysis["details"]:
            st.dataframe(analysis["details"], hide_index=True, width="stretch")
        for document in detail["documents"]:
            with st.expander(document["id"] + " · " + document["type"]):
                st.json(document)
        if analysis["graph"]:
            st.subheader("Transaction chain")
            st.dataframe(analysis["graph"], hide_index=True, width="stretch")
    with narrative:
        st.write(analysis["draft"])
        report = json.dumps(engine.report(uid, ident), indent=2, ensure_ascii=False)
        st.download_button("Download internal demo report", report,
                           file_name=ident + "-internal-report.json", mime="application/json")
        st.caption(detail["connector"]["message"])
    with workflow:
        enabled = {action["id"]: action for action in detail["actions"] if action["enabled"]}
        for action in detail["actions"]:
            if not action["enabled"]:
                st.caption(action["label"] + " — " + action["why"])
        if enabled:
            with st.form("action_" + ident + "_" + str(detail["case"]["version"])):
                action = st.selectbox("Action", list(enabled), format_func=lambda a: enabled[a]["label"])
                references = st.multiselect("Supporting evidence", list(dict.fromkeys(analysis["evidence_ids"])))
                rationale = st.text_area("Review rationale (at least 20 characters)", max_chars=1200)
                submit = st.form_submit_button("Review change")
            if submit:
                draft = engine.validate_action(uid, {"id": ident, "version": detail["case"]["version"],
                    "action": action, "evidence": references, "reason": rationale})
                review("action", draft, uid)
                st.rerun()
        else:
            st.info("No actions available to this persona in the current case state.")
    with history:
        st.dataframe(detail["events"], hide_index=True, width="stretch")


try:
    app()
except (ValidationError, ConflictError, NotFoundError) as error:
    st.error(str(error))
    st.caption("Correct the form or refresh the case and review again.")
