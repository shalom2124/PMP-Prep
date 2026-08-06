import streamlit as st
import time
from pathlib import Path

st.set_page_config(
    page_title="PMP Prep",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Load CSS
css_path = Path(__file__).parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

# ── Navigation ──────────────────────────────────────────────────────────────
PAGES = {
    "📊 Dashboard": "dashboard",
    "🎯 Quiz": "quiz",
    "🃏 Flashcards": "flashcards",
    "📈 Analytics": "analytics",
    "⚙️ Settings": "settings",
}

with st.sidebar:
    st.markdown("## 📋 PMP Prep")
    st.markdown("---")
    selection = st.radio("Navigate", list(PAGES.keys()), label_visibility="collapsed")
    st.markdown("---")
    from modules.progress import get_overall_readiness, get_streak
    readiness = get_overall_readiness()
    streak = get_streak()
    st.metric("Readiness", f"{readiness}%")
    st.metric("Day Streak", f"{streak} 🔥" if streak > 0 else "0")

page = PAGES[selection]


# ════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ════════════════════════════════════════════════════════════════════════════
def _render_dashboard():
    st.title("📊 Dashboard")
    from modules.progress import (
        get_overall_readiness, get_domain_accuracy, get_weak_topics,
        get_streak, get_sessions
    )

    readiness = get_overall_readiness()
    streak = get_streak()
    sessions = get_sessions()
    domain_acc = get_domain_accuracy()
    weak = get_weak_topics()

    col1, col2, col3 = st.columns(3)
    with col1:
        color = "green" if readiness >= 70 else "orange" if readiness >= 55 else "red"
        st.markdown(
            f'<div class="readiness-score" style="color:{color}">{readiness}%</div>'
            f'<div style="text-align:center;color:#666">Exam Readiness</div>',
            unsafe_allow_html=True,
        )
    with col2:
        st.metric("Sessions Completed", len(sessions))
    with col3:
        st.metric("Day Streak", f"{streak} 🔥" if streak else str(streak))

    st.markdown("---")

    # Domain progress
    st.subheader("Domain Accuracy")
    DOMAIN_WEIGHTS = {"People": 42, "Process": 50, "Business Environment": 8}
    for domain, weight in DOMAIN_WEIGHTS.items():
        acc = domain_acc.get(domain, 0)
        color = "normal" if acc >= 70 else "off"
        col_d, col_p = st.columns([3, 1])
        with col_d:
            st.progress(int(acc), text=f"**{domain}** ({weight}% of exam) — {acc}%")
        with col_p:
            if acc < 70:
                st.markdown('<span class="weak-badge">Needs work</span>', unsafe_allow_html=True)

    # Weak areas
    if weak:
        st.markdown("---")
        st.subheader("⚠️ Weak Areas (< 70%)")
        cols = st.columns(min(len(weak), 3))
        for i, w in enumerate(weak[:6]):
            with cols[i % 3]:
                st.error(f"**{w['subtopic']}**\n\n{w['pct']}% correct ({w['total']} attempts)")
    else:
        if sessions:
            st.success("No weak areas detected! Keep going.")

    st.markdown("---")
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("▶ Quick 10 Questions", use_container_width=True, type="primary"):
            st.session_state["quiz_mode"] = "quick10"
            st.session_state["page_override"] = "quiz"
            st.rerun()
    with col_b:
        if weak and st.button("🎯 Drill Weak Areas", use_container_width=True):
            st.session_state["quiz_mode"] = "weak"
            st.session_state["page_override"] = "quiz"
            st.rerun()

    if not sessions:
        st.info("👋 No study data yet. Start a quiz to track your progress!")


# ════════════════════════════════════════════════════════════════════════════
# QUIZ
# ════════════════════════════════════════════════════════════════════════════
def _render_quiz():
    st.title("🎯 Quiz")
    from modules.quiz import (
        get_questions_for_mock, get_questions_by_domain, get_questions_by_topic,
        get_questions_for_weak_areas, get_quick_10, get_all_domains, get_all_topics,
        check_answer, score_session, load_questions,
    )
    from modules.progress import record_answer, record_session, get_weak_topics
    from modules import ai_generator

    # Mode selector (or use override from dashboard)
    override = st.session_state.pop("quiz_mode", None)

    mode_options = ["Mock Exam (180 Q)", "Domain Practice", "Topic Drill", "Weak Area Focus", "Quick 10"]
    if override == "quick10":
        default_idx = 4
    elif override == "weak":
        default_idx = 3
    else:
        default_idx = 0

    mode = st.selectbox("Select Quiz Mode", mode_options, index=default_idx)

    # ── Mode config ──────────────────────────────────────────────────────────
    questions = []
    show_timer = False
    timer_seconds = 0
    quiz_label = mode

    all_q = load_questions()

    if mode == "Mock Exam (180 Q)":
        if st.button("Start Mock Exam", type="primary"):
            questions = get_questions_for_mock(180)
            st.session_state["active_quiz"] = questions
            st.session_state["quiz_label"] = "Mock Exam"
            st.session_state["quiz_results"] = []
            st.session_state["quiz_idx"] = 0
            st.session_state["mock_start_time"] = time.time()
        show_timer = True
        timer_seconds = 230 * 60

    elif mode == "Domain Practice":
        domains = get_all_domains(all_q)
        domain = st.selectbox("Domain", domains)
        count = st.select_slider("Questions", [10, 20, 40], value=20)
        if st.button("Start", type="primary"):
            questions = get_questions_by_domain(domain, count)
            st.session_state["active_quiz"] = questions
            st.session_state["quiz_label"] = f"Domain: {domain}"
            st.session_state["quiz_results"] = []
            st.session_state["quiz_idx"] = 0

    elif mode == "Topic Drill":
        domains = get_all_domains(all_q)
        domain = st.selectbox("Domain", domains, key="td_domain")
        topics = get_all_topics(domain, all_q)
        topic = st.selectbox("Topic", topics)
        count = st.select_slider("Questions", [10, 20, 40], value=20, key="td_count")
        if st.button("Start", type="primary"):
            questions = get_questions_by_topic(topic, count)
            st.session_state["active_quiz"] = questions
            st.session_state["quiz_label"] = f"Topic: {topic}"
            st.session_state["quiz_results"] = []
            st.session_state["quiz_idx"] = 0

        # AI generate button
        if ai_generator.is_available() and topics:
            st.markdown("---")
            if st.button(f"✨ Generate 10 AI Questions for '{topic}'"):
                with st.spinner("Generating questions with Claude..."):
                    new_q = ai_generator.generate_questions(topic, domain, 10)
                if new_q:
                    st.success(f"Added {len(new_q)} new questions to the bank!")
                else:
                    st.error("Generation failed. Check your API key or try again.")

    elif mode == "Weak Area Focus":
        weak = get_weak_topics()
        if not weak:
            st.info("No weak areas yet — answer at least 5 questions per topic first.")
        else:
            st.write("Auto-targeting topics below 70%:")
            for w in weak[:5]:
                st.markdown(f"- **{w['subtopic']}** ({w['pct']}%)")
            count = st.select_slider("Questions", [10, 20, 40], value=20, key="wa_count")
            if st.button("Start Weak Area Drill", type="primary"):
                questions = get_questions_for_weak_areas(weak, count)
                st.session_state["active_quiz"] = questions
                st.session_state["quiz_label"] = "Weak Area Focus"
                st.session_state["quiz_results"] = []
                st.session_state["quiz_idx"] = 0

            if ai_generator.is_available() and weak:
                st.markdown("---")
                if st.button(f"✨ Generate AI Questions for Weakest Topic ('{weak[0]['subtopic']}')"):
                    with st.spinner("Generating..."):
                        new_q = ai_generator.generate_questions(weak[0]["subtopic"], weak[0]["domain"], 10)
                    if new_q:
                        st.success(f"Added {len(new_q)} new AI questions!")
                    else:
                        st.error("Generation failed.")

    elif mode == "Quick 10":
        if st.button("Start Quick 10", type="primary"):
            questions = get_quick_10()
            st.session_state["active_quiz"] = questions
            st.session_state["quiz_label"] = "Quick 10"
            st.session_state["quiz_results"] = []
            st.session_state["quiz_idx"] = 0

    # ── Active quiz loop ─────────────────────────────────────────────────────
    if "active_quiz" not in st.session_state:
        return

    active_q = st.session_state["active_quiz"]
    results = st.session_state.get("quiz_results", [])
    idx = st.session_state.get("quiz_idx", 0)

    # Quiz complete
    if idx >= len(active_q):
        _render_score_report(results, st.session_state.get("quiz_label", mode))
        if st.button("Start New Quiz"):
            for k in ["active_quiz", "quiz_results", "quiz_idx", "quiz_label", "mock_start_time", "submitted_answer"]:
                st.session_state.pop(k, None)
            st.rerun()
        return

    # Timer (mock exam)
    immediate = st.session_state.get("feedback_immediate", True)
    if mode == "Mock Exam (180 Q)" and "mock_start_time" in st.session_state:
        elapsed = time.time() - st.session_state["mock_start_time"]
        remaining = max(0, timer_seconds - elapsed)
        mins, secs = divmod(int(remaining), 60)
        st.markdown(f"⏱️ **Time remaining: {mins:02d}:{secs:02d}**")
        if remaining == 0:
            st.warning("Time's up! Submitting your exam.")
            st.session_state["quiz_idx"] = len(active_q)
            st.rerun()

    # Progress
    q = active_q[idx]
    st.markdown(f"**Question {idx + 1} of {len(active_q)}** | {q['domain']} › {q['topic']}")
    st.progress((idx) / len(active_q))

    # Question
    st.markdown(f"### {q['question']}")
    difficulty_icon = {"easy": "🟢", "medium": "🟡", "hard": "🔴"}.get(q.get("difficulty", "medium"), "🟡")
    st.caption(f"{difficulty_icon} {q.get('difficulty', 'medium').title()} | {q.get('type', 'multiple_choice').replace('_', ' ').title()}")

    # Answer input
    submitted = st.session_state.get("submitted_answer")
    options = q["options"]

    if q.get("type") == "multiple_select":
        correct_list = q["answer"] if isinstance(q["answer"], list) else [q["answer"]]
        n_correct = len(correct_list)
        st.caption(f"Select **{n_correct}** answers")
        user_choices = []
        for key, val in options.items():
            if st.checkbox(f"**{key}.** {val}", key=f"ms_{idx}_{key}", disabled=submitted is not None):
                user_choices.append(key)
        if submitted is None:
            if len(user_choices) == n_correct:
                if st.button("Submit Answer", type="primary"):
                    is_correct = check_answer(q, user_choices)
                    st.session_state["submitted_answer"] = (user_choices, is_correct)
                    record_answer(q["domain"], q["topic"], q.get("subtopic", ""), is_correct)
                    if not immediate:
                        st.session_state["quiz_results"].append({"question": q, "correct": is_correct, "user_answer": user_choices})
                    st.rerun()
            else:
                st.button("Submit Answer", disabled=True, type="primary")
    else:
        cols = st.columns(1)
        user_answer = None
        for key, val in options.items():
            btn_label = f"**{key}.** {val}"
            if submitted is None:
                if st.button(btn_label, key=f"opt_{idx}_{key}", use_container_width=True):
                    is_correct = check_answer(q, key)
                    st.session_state["submitted_answer"] = (key, is_correct)
                    record_answer(q["domain"], q["topic"], q.get("subtopic", ""), is_correct)
                    if not immediate:
                        st.session_state["quiz_results"].append({"question": q, "correct": is_correct, "user_answer": key})
                    st.rerun()
            else:
                chosen, is_correct = submitted
                correct_key = q["answer"]
                if key == correct_key:
                    st.markdown(f'<div class="answer-correct">✅ {btn_label}</div>', unsafe_allow_html=True)
                elif key == chosen and not is_correct:
                    st.markdown(f'<div class="answer-wrong">❌ {btn_label}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f"{btn_label}")

    # Feedback (immediate mode)
    if submitted is not None and immediate:
        chosen, is_correct = submitted
        if is_correct:
            st.success("✅ Correct!")
        else:
            st.error(f"❌ Incorrect. The correct answer is **{q['answer']}**.")
        with st.expander("📖 Explanation", expanded=True):
            st.markdown(q.get("explanation", "No explanation provided."))

        if st.button("Next Question →", type="primary"):
            st.session_state["quiz_results"].append({"question": q, "correct": is_correct, "user_answer": chosen})
            st.session_state["quiz_idx"] = idx + 1
            st.session_state.pop("submitted_answer", None)
            st.rerun()
    elif submitted is not None and not immediate:
        chosen, is_correct = submitted
        if st.button("Next Question →", type="primary"):
            st.session_state["quiz_idx"] = idx + 1
            st.session_state.pop("submitted_answer", None)
            st.rerun()


def _render_score_report(results: list, label: str):
    from modules.quiz import score_session
    from modules.progress import record_session

    summary = score_session(results)
    record_session(summary["correct"], summary["total"], label, summary["domains"])

    st.markdown("---")
    st.subheader(f"📋 Score Report — {label}")
    col1, col2, col3 = st.columns(3)
    pct = summary["pct"]
    color = "green" if pct >= 70 else "orange" if pct >= 55 else "red"
    with col1:
        st.markdown(
            f'<div class="readiness-score" style="color:{color}">{pct}%</div>'
            f'<div style="text-align:center">{summary["correct"]} / {summary["total"]} correct</div>',
            unsafe_allow_html=True,
        )
    with col2:
        verdict = "✅ PASS (estimate)" if pct >= 70 else "⚠️ BORDERLINE" if pct >= 55 else "❌ NEEDS MORE PREP"
        st.markdown(f"**Estimate:** {verdict}")
    with col3:
        st.markdown("**Domain Breakdown**")
        for d, s in summary["domains"].items():
            icon = "✅" if s["pct"] >= 70 else "⚠️"
            st.markdown(f"{icon} {d}: {s['pct']}%")

    # Show explanations for wrong answers if end-of-quiz mode
    if not st.session_state.get("feedback_immediate", True):
        st.markdown("---")
        st.subheader("Review Incorrect Answers")
        wrong = [r for r in results if not r["correct"]]
        for r in wrong:
            q = r["question"]
            with st.expander(f"❌ {q['question'][:80]}..."):
                st.markdown(f"**Your answer:** {r['user_answer']} | **Correct:** {q['answer']}")
                st.markdown(q.get("explanation", ""))


# ════════════════════════════════════════════════════════════════════════════
# FLASHCARDS
# ════════════════════════════════════════════════════════════════════════════
def _render_flashcards():
    import json
    st.title("🃏 Flashcards")

    fc_path = Path(__file__).parent / "data" / "flashcards.json"
    if not fc_path.exists():
        st.warning("Flashcard data not found.")
        return

    with open(fc_path) as f:
        all_cards = json.load(f)

    # Filter
    groups = sorted({c["group"] for c in all_cards})
    selected_group = st.selectbox("Category", ["All"] + groups)
    if selected_group != "All":
        cards = [c for c in all_cards if c["group"] == selected_group]
    else:
        cards = all_cards

    known = st.session_state.get("known_cards", set())
    remaining = [c for c in cards if c["id"] not in known]

    st.caption(f"{len(remaining)} cards remaining | {len(known)} marked as known")

    if not remaining:
        st.success("🎉 You've reviewed all cards in this category!")
        if st.button("Reset Known Cards"):
            st.session_state["known_cards"] = set()
            st.rerun()
        return

    # Card navigation
    if "fc_idx" not in st.session_state or st.session_state.get("fc_group") != selected_group:
        st.session_state["fc_idx"] = 0
        st.session_state["fc_group"] = selected_group
        st.session_state["fc_flipped"] = False

    idx = st.session_state["fc_idx"] % len(remaining)
    card = remaining[idx]
    flipped = st.session_state.get("fc_flipped", False)

    col_prev, col_flip, col_next = st.columns([1, 2, 1])
    with col_prev:
        if st.button("← Prev"):
            st.session_state["fc_idx"] = max(0, idx - 1)
            st.session_state["fc_flipped"] = False
            st.rerun()
    with col_flip:
        if st.button("🔄 Flip Card", use_container_width=True, type="primary"):
            st.session_state["fc_flipped"] = not flipped
            st.rerun()
    with col_next:
        if st.button("Next →"):
            st.session_state["fc_idx"] = (idx + 1) % len(remaining)
            st.session_state["fc_flipped"] = False
            st.rerun()

    # Card display
    if not flipped:
        st.markdown(
            f'<div class="flashcard"><div><div style="font-size:0.8rem;opacity:0.7;margin-bottom:0.5rem">{card["group"]}</div>'
            f'<div>{card["front"]}</div></div></div>',
            unsafe_allow_html=True,
        )
        st.caption("Click Flip to see the answer")
    else:
        st.markdown(
            f'<div class="flashcard" style="background: linear-gradient(135deg, #155724 0%, #1e7e34 100%);">'
            f'<div>{card["back"]}</div></div>',
            unsafe_allow_html=True,
        )
        col_know, _ = st.columns([1, 3])
        with col_know:
            if st.button("✅ Mark as Known"):
                known.add(card["id"])
                st.session_state["known_cards"] = known
                st.session_state["fc_flipped"] = False
                st.rerun()

    st.markdown(f"Card {idx + 1} of {len(remaining)}")


# ════════════════════════════════════════════════════════════════════════════
# ANALYTICS
# ════════════════════════════════════════════════════════════════════════════
def _render_analytics():
    st.title("📈 Analytics")
    from modules.analytics import score_trend_chart, domain_accuracy_chart, topic_heatmap_table, most_missed_questions

    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(score_trend_chart(), use_container_width=True)
    with col2:
        st.plotly_chart(domain_accuracy_chart(), use_container_width=True)

    st.markdown("---")
    st.subheader("Topic Accuracy Breakdown")
    df = topic_heatmap_table()
    if df.empty:
        st.info("No data yet — complete some quizzes first.")
    else:
        def _color_accuracy(val):
            if val >= 70:
                return "background-color: #c6efce; color: #276221"
            elif val >= 55:
                return "background-color: #ffeb9c; color: #9c6500"
            else:
                return "background-color: #ffc7ce; color: #9c0006"

        st.dataframe(
            df.style.map(_color_accuracy, subset=["Accuracy %"]),
            use_container_width=True,
            hide_index=True,
        )

    st.markdown("---")
    st.subheader("Most Missed Questions")
    missed = most_missed_questions(10)
    if not missed:
        st.info("Answer at least 3 questions per topic to see most-missed analysis.")
    else:
        for q in missed:
            with st.expander(f"❌ {q['_accuracy']}% — {q['question'][:90]}..."):
                st.markdown(f"**Domain:** {q['domain']} | **Topic:** {q['topic']}")
                st.markdown(f"**Correct answer:** {q['answer']}")
                st.markdown(q.get("explanation", ""))


# ════════════════════════════════════════════════════════════════════════════
# SETTINGS
# ════════════════════════════════════════════════════════════════════════════
def _render_settings():
    st.title("⚙️ Settings")

    st.subheader("Quiz Behavior")
    immediate = st.toggle(
        "Show feedback immediately after each answer",
        value=st.session_state.get("feedback_immediate", True),
    )
    st.session_state["feedback_immediate"] = immediate
    st.caption("Off = review all answers at the end (simulates real exam experience)")

    st.markdown("---")
    st.subheader("AI Question Generation (Optional)")
    st.markdown(
        "Add your Anthropic API key to enable AI-generated practice questions for weak areas. "
        "The app works fully without this."
    )

    import os
    from modules import ai_generator
    env_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if env_key:
        st.success("✅ API key detected from environment variable `ANTHROPIC_API_KEY`.")
    else:
        manual_key = st.text_input("Anthropic API key", type="password", placeholder="sk-ant-...")
        if manual_key:
            os.environ["ANTHROPIC_API_KEY"] = manual_key
            st.success("API key set for this session.")

    st.markdown("---")
    st.subheader("Data")
    from modules.progress import get_sessions
    sessions = get_sessions()
    st.info(f"You have **{len(sessions)} session(s)** recorded.")
    if st.button("⚠️ Reset All Progress", type="secondary"):
        confirm = st.checkbox("Yes, I want to delete all my progress data")
        if confirm:
            from pathlib import Path
            p = Path(__file__).parent / "user_data" / "progress.json"
            if p.exists():
                p.unlink()
            st.success("Progress reset.")
            st.rerun()


# ── Page routing (after all functions defined) ───────────────────────────────
if page == "dashboard":
    _render_dashboard()
elif page == "quiz":
    _render_quiz()
elif page == "flashcards":
    _render_flashcards()
elif page == "analytics":
    _render_analytics()
elif page == "settings":
    _render_settings()
