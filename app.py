# app.py
import streamlit as st
from database import init_db, create_user, get_user_by_username, hash_password, get_user_by_id, get_conn
import database
import recommender
import utils
import pandas as pd
from datetime import datetime
from fpdf import FPDF
import io

st.set_page_config(page_title="Adaptive Learning Path", layout="wide")
init_db()

# ---------- Auth helpers ----------
def login(username, password):
    user = get_user_by_username(username)
    if not user:
        return None
    if user["password_hash"] == database.hash_password(password):
        return user
    return None

def register_user(username, name, regno, email, password, role):
    return database.create_user(username, name, regno, email, password, role)

# ---------- DB helpers ----------
def fetch_all_students():
    conn = get_conn()
    df = pd.read_sql_query("SELECT id,username,name,regno,email FROM users WHERE role='student'", conn)
    conn.close()
    return df

def fetch_marks_for_student(sid):
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM marks WHERE user_id=? ORDER BY created_at DESC", conn, params=(sid,))
    conn.close()
    return df

def save_marks(user_id, internal, c1o,c1m,c2o,c2m,c3o,c3m):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""INSERT INTO marks (user_id,internal,co1_obt,co1_max,co2_obt,co2_max,co3_obt,co3_max)
                VALUES (?,?,?,?,?,?,?,?)""",
                (user_id,internal, c1o,c1m,c2o,c2m,c3o,c3m))
    conn.commit()
    conn.close()

def add_question(student_id, co, question_text):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO questions (student_id,co,question) VALUES (?,?,?)",
               (student_id, co, question_text))
    conn.commit()
    qid = cur.lastrowid
    conn.close()
    # notify staff via email (use email column)
    conn = get_conn()
    staff = conn.execute("SELECT email,name FROM users WHERE role='staff'").fetchall()
    conn.close()
    for s in staff:
        if s["email"]:
            to = s["email"]
            subject = f"New question from student {student_id}"
            body = f"Student {student_id} asked a question on {co}:\n\n{question_text}\n\nOpen the app to answer."
            utils.send_email(to, subject, body)
    return qid

def staff_answer_question(question_id, staff_id, answer_text):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO answers (question_id, staff_id, answer) VALUES (?,?,?)",
               (question_id, staff_id, answer_text))
    cur.execute("UPDATE questions SET answered=1 WHERE id=?", (question_id,))
    conn.commit()
    # notify student
    cur.execute("SELECT q.student_id, u.email FROM questions q JOIN users u ON q.student_id=u.id WHERE q.id=?", (question_id,))
    row = cur.fetchone()
    conn.close()
    if row and row[1]:
        utils.send_email(row[1], "Staff answered your question", f"Answer:\n\n{answer_text}")
    return True

def add_resource(staff_id, co, title, rtype, url, notes):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO resources (staff_id,co,title,type,url,notes) VALUES (?,?,?,?,?,?)",
               (staff_id, co, title, rtype, url, notes))
    conn.commit()
    conn.close()

def update_resource(res_id, title, rtype, url, notes):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE resources SET title=?, type=?, url=?, notes=? WHERE id=?",
               (title, rtype, url, notes, res_id))
    conn.commit()
    conn.close()

def delete_resource(res_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM resources WHERE id=?", (res_id,))
    conn.commit()
    conn.close()

def fetch_resources_for_co(co):
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM resources WHERE co=? ORDER BY created_at DESC", conn, params=(co,))
    conn.close()
    return df

# ---------- PDF export ----------
def generate_student_pdf(student_row, analysis, marks_table):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(0,10, "Adaptive Learning Path - Student Report", ln=True, align="C")
    pdf.ln(5)
    pdf.cell(0,8, f"Name: {student_row['name']} ({student_row['regno']})", ln=True)
    pdf.cell(0,8, f"Email: {student_row.get('email','')}", ln=True)
    pdf.cell(0,8, f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True)
    pdf.ln(5)
    pdf.cell(0,8, "Marks (latest entries):", ln=True)
    pdf.ln(3)
    # marks table text
    for idx, r in marks_table.iterrows():
        pdf.cell(0,6, f"Internal {r['internal']} | CO1: {r['co1_obt']}/{r['co1_max']} | CO2: {r['co2_obt']}/{r['co2_max']} | CO3: {r['co3_obt']}/{r['co3_max']} | {r['created_at']}", ln=True)
    pdf.ln(4)
    pdf.cell(0,8, "Analysis & Plans:", ln=True)
    for co, info in analysis.items():
        pdf.multi_cell(0,6, f"{co}: Avg {info['avg']}% | Gap {info['gap']}% | Severity: {info['severity']}")
        plan = recommender.generate_learning_plan(co, info['severity'])
        for p in plan["plan"]:
            pdf.multi_cell(0,6, f" - {p}")
        if plan["resources"]:
            pdf.multi_cell(0,6, " Resources:")
            for r in plan["resources"]:
                pdf.multi_cell(0,6, f"   * {r['title']} ({r['type']}) -> {r['url']}")
    # return bytes
    return pdf.output(dest='S').encode('latin-1')

# ---------- UI ----------
st.title("Adaptive Learning Path — Student & Staff Portal (Updated)")

menu = ["Login","Register","About"]
choice = st.sidebar.selectbox("Menu", menu)

if "user" not in st.session_state:
    st.session_state.user = None

if choice == "About":
    st.info("Full system with resource edit/delete, PDF export, email notifications (if configured).")
    st.markdown("Demo accounts: staff1/staffpass (email staff1@example.com), student1/studentpass (student1@example.com)")

elif choice == "Register":
    st.subheader("Register")
    role = st.selectbox("Register as", ["student","staff"])
    username = st.text_input("Username (unique id)")
    name = st.text_input("Name")
    regno = st.text_input("Reg No (optional)")
    email = st.text_input("Email (for notifications)")
    password = st.text_input("Password", type="password")
    if st.button("Create account"):
        ok = register_user(username, name, regno, email, password, role)
        if ok:
            st.success("Account created. Please login.")
        else:
            st.error("Account creation failed (maybe username exists).")

elif choice == "Login":
    st.subheader("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        user = login(username, password)
        if user:
            st.session_state.user = dict(user)
            st.success(f"Logged in as {user['name']} ({user['role']})")
        else:
            st.error("Invalid credentials")

    if st.session_state.user:
        user = st.session_state.user
        st.sidebar.markdown(f"**Logged in as:** {user['name']} ({user['role']})")
        if st.button("Logout"):
            st.session_state.user = None
            st.experimental_rerun()

        if user["role"] == "student":
            st.header("Student Dashboard")
            st.markdown("Submit marks and ask questions for weak COs.")
            col1,col2 = st.columns(2)
            with col1:
                st.subheader("Internal 1")
                i1_c1o = st.number_input("I1 CO1 obtained", value=0.0, key="i1_c1o")
                i1_c1m = st.number_input("I1 CO1 max", value=25.0, key="i1_c1m")
                i1_c2o = st.number_input("I1 CO2 obtained", value=0.0, key="i1_c2o")
                i1_c2m = st.number_input("I1 CO2 max", value=25.0, key="i1_c2m")
                i1_c3o = st.number_input("I1 CO3 obtained", value=0.0, key="i1_c3o")
                i1_c3m = st.number_input("I1 CO3 max", value=25.0, key="i1_c3m")
            with col2:
                st.subheader("Internal 2")
                i2_c1o = st.number_input("I2 CO1 obtained", value=0.0, key="i2_c1o")
                i2_c1m = st.number_input("I2 CO1 max", value=25.0, key="i2_c1m")
                i2_c2o = st.number_input("I2 CO2 obtained", value=0.0, key="i2_c2o")
                i2_c2m = st.number_input("I2 CO2 max", value=25.0, key="i2_c2m")
                i2_c3o = st.number_input("I2 CO3 obtained", value=0.0, key="i2_c3o")
                i2_c3m = st.number_input("I2 CO3 max", value=25.0, key="i2_c3m")
            if st.button("Save marks"):
                save_marks(user["id"], 1, i1_c1o,i1_c1m,i1_c2o,i1_c2m,i1_c3o,i1_c3m)
                save_marks(user["id"], 2, i2_c1o,i2_c1m,i2_c2o,i2_c2m,i2_c3o,i2_c3m)
                st.success("Marks saved.")

            st.markdown("---")
            st.subheader("Latest summary & recommendations")
            dfm = fetch_marks_for_student(user["id"])
            if dfm.empty:
                st.info("No marks saved yet.")
            else:
                latest = dfm.iloc[0].to_dict()
                marks_row = {
                    "i1_co1_obt": latest["co1_obt"], "i1_co1_max": latest["co1_max"],
                    "i1_co2_obt": latest["co2_obt"], "i1_co2_max": latest["co2_max"],
                    "i1_co3_obt": latest["co3_obt"], "i1_co3_max": latest["co3_max"],
                    "i2_co1_obt": dfm.iloc[1]["co1_obt"] if len(dfm)>1 else 0, "i2_co1_max": dfm.iloc[1]["co1_max"] if len(dfm)>1 else 0,
                    "i2_co2_obt": dfm.iloc[1]["co2_obt"] if len(dfm)>1 else 0, "i2_co2_max": dfm.iloc[1]["co2_max"] if len(dfm)>1 else 0,
                    "i2_co3_obt": dfm.iloc[1]["co3_obt"] if len(dfm)>1 else 0, "i2_co3_max": dfm.iloc[1]["co3_max"] if len(dfm)>1 else 0,
                }
                analysis = recommender.analyze_marks_dict(marks_row)
                for co, info in analysis.items():
                    st.markdown(f"**{co}** — Avg {info['avg']}% — Gap {info['gap']}% — Severity: {info['severity']}")
                    plan = recommender.generate_learning_plan(co, info['severity'])
                    for p in plan["plan"]:
                        st.write("- ", p)
                    if plan["resources"]:
                        st.write("Resources:")
                        for r in plan["resources"]:
                            if r["type"]=="video":
                                st.write(f"- {r['title']} (Video) — {r['notes']}")
                                st.video(r["url"])
                            else:
                                st.write(f"- {r['title']} — {r['url']}")

                st.markdown("---")
                # ask question if weak
                low_cos = [c for c,i in analysis.items() if i["severity"] in ("low","medium","high")]
                if low_cos:
                    st.subheader("Ask questions about weak COs")
                    sel_co = st.selectbox("Select CO", low_cos)
                    qtext = st.text_area("Write your question (what difficulty, which topics?)")
                    if st.button("Submit question"):
                        qid = add_question(user["id"], sel_co, qtext)
                        st.success("Question submitted to staff.")
                else:
                    st.info("No weak COs detected — good job!")

                st.markdown("---")
                st.subheader("Export printable report (PDF)")
                student_row = get_user_by_id(user["id"])
                if st.button("Generate PDF report"):
                    pdf_bytes = generate_student_pdf(student_row, analysis, dfm.head(5))
                    st.download_button("Download PDF", data=pdf_bytes, file_name=f"{student_row['name']}_report.pdf", mime="application/pdf")

                st.markdown("---")
                st.subheader("Submit activity update (homework/quiz/video)")
                a_type = st.selectbox("Activity type", ["video","quiz","homework","assessment"])
                details = st.text_input("Details (e.g. link or comment)")
                if st.button("Submit activity update"):
                    conn = get_conn()
                    cur = conn.cursor()
                    cur.execute("INSERT INTO activities (student_id, activity_type, details, status) VALUES (?,?,?,?)",
                               (user["id"], a_type, details, "done"))
                    conn.commit()
                    conn.close()
                    st.success("Activity update saved.")
                    # notify staff
                    conn = get_conn()
                    stafflist = conn.execute("SELECT email,name FROM users WHERE role='staff'").fetchall()
                    conn.close()
                    for s in stafflist:
                        if s["email"]:
                            utils.send_email(s["email"], f"Student {user['name']} updated activity", f"{user['name']} submitted: {a_type}\nDetails: {details}")

        elif user["role"] == "staff":
            st.header("Staff Dashboard")
            st.subheader("Students list")
            students_df = fetch_all_students()
            st.dataframe(students_df)

            st.markdown("---")
            st.subheader("Select a student to view marks & generate report")
            sid = st.selectbox("Select student id", students_df["id"].tolist())
            if sid:
                student = database.get_user_by_id(sid)
                st.markdown(f"**{student['name']} ({student['regno']}) Email: {student['email']}**")
                marks = fetch_marks_for_student(sid)
                if marks.empty:
                    st.info("No marks yet.")
                else:
                    st.write("Marks history (latest first)")
                    st.dataframe(marks)
                    latest = marks.iloc[0].to_dict()
                    marks_row = {
                        "i1_co1_obt": latest["co1_obt"], "i1_co1_max": latest["co1_max"],
                        "i1_co2_obt": latest["co2_obt"], "i1_co2_max": latest["co2_max"],
                        "i1_co3_obt": latest["co3_obt"], "i1_co3_max": latest["co3_max"],
                        "i2_co1_obt": marks.iloc[1]["co1_obt"] if len(marks)>1 else 0, "i2_co1_max": marks.iloc[1]["co1_max"] if len(marks)>1 else 0,
                        "i2_co2_obt": marks.iloc[1]["co2_obt"] if len(marks)>1 else 0, "i2_co2_max": marks.iloc[1]["co2_max"] if len(marks)>1 else 0,
                        "i2_co3_obt": marks.iloc[1]["co3_obt"] if len(marks)>1 else 0, "i2_co3_max": marks.iloc[1]["co3_max"] if len(marks)>1 else 0,
                    }
                    analysis = recommender.analyze_marks_dict(marks_row)
                    st.write(analysis)
                    for co,info in analysis.items():
                        plan = recommender.generate_learning_plan(co, info["severity"])
                        st.write(f"**{co}** -> {info} ")
                        for p in plan["plan"]:
                            st.write("- ", p)
                        res_df = fetch_resources_for_co(co)
                        if not res_df.empty:
                            st.write("Resources (DB):")
                            st.dataframe(res_df[["id","title","type","url","notes","created_at"]])

                    # Generate student PDF
                    if st.button("Generate & download student PDF"):
                        pdf_bytes = generate_student_pdf(student, analysis, marks.head(5))
                        st.download_button("Download student PDF", data=pdf_bytes, file_name=f"{student['name']}_report.pdf", mime="application/pdf")

            st.markdown("---")
            st.subheader("Student Questions")
            conn = get_conn()
            qdf = pd.read_sql_query("SELECT q.*, u.name as student_name, u.email as student_email FROM questions q LEFT JOIN users u ON q.student_id=u.id ORDER BY answered ASC, created_at DESC", conn)
            conn.close()
            if qdf.empty:
                st.write("No questions.")
            else:
                st.dataframe(qdf[["id","student_name","co","question","answered","created_at"]])
                qid = st.number_input("Enter question id to answer", min_value=0, value=0, step=1)
                ans_text = st.text_area("Answer text")
                if st.button("Submit Answer"):
                    if qid>0 and ans_text.strip():
                        staff_answer_question(qid, user["id"], ans_text)
                        st.success("Answer saved and student notified (if email exists).")
                    else:
                        st.error("Provide question id and answer.")

            st.markdown("---")
            st.subheader("Add / Edit / Delete Resource")
            r_co = st.selectbox("CO for resource", ["CO1","CO2","CO3"])
            r_title = st.text_input("Title", key="new_r_title")
            r_type = st.selectbox("Type", ["video","pdf","text","quiz"], key="new_r_type")
            r_url = st.text_input("URL (YouTube link or file link)", key="new_r_url")
            r_notes = st.text_area("Notes", key="new_r_notes")
            if st.button("Add resource"):
                add_resource(user["id"], r_co, r_title, r_type, r_url, r_notes)
                st.success("Resource added.")

            st.markdown("## Edit / Delete existing resource")
            co_sel = st.selectbox("Select CO to manage resources", ["CO1","CO2","CO3"], key="manage_co")
            res_df = fetch_resources_for_co(co_sel)
            if res_df.empty:
                st.write("No resources for selected CO.")
            else:
                st.dataframe(res_df[["id","title","type","url","notes","created_at"]])
                rid = st.number_input("Enter resource id to edit/delete", min_value=0, value=0, step=1)
                new_title = st.text_input("New title", key="edit_title")
                new_type = st.selectbox("New type", ["video","pdf","text","quiz"], key="edit_type")
                new_url = st.text_input("New URL", key="edit_url")
                new_notes = st.text_area("New notes", key="edit_notes")
                if st.button("Update resource"):
                    if rid>0:
                        update_resource(rid, new_title, new_type, new_url, new_notes)
                        st.success("Resource updated.")
                    else:
                        st.error("Provide valid resource id.")
                if st.button("Delete resource"):
                    if rid>0:
                        delete_resource(rid)
                        st.success("Resource deleted.")
                    else:
                        st.error("Provide valid resource id.")

            st.markdown("---")
            st.subheader("Student activities (pending/done)")
            conn = get_conn()
            act = pd.read_sql_query("SELECT a.*, u.name as student_name FROM activities a LEFT JOIN users u ON a.student_id=u.id ORDER BY created_at DESC", conn)
            conn.close()
            if not act.empty:
                st.dataframe(act)
                aid = st.number_input("Enter activity id to mark reviewed", min_value=0, value=0)
                if st.button("Mark activity reviewed"):
                    if aid>0:
                        conn = get_conn()
                        cur = conn.cursor()
                        cur.execute("UPDATE activities SET status='reviewed' WHERE id=?", (aid,))
                        conn.commit()
                        conn.close()
                        st.success("Activity marked reviewed.")
            else:
                st.write("No activities yet.")

            st.markdown("---")
            st.subheader("Export students CSV")
            if st.button("Export students CSV"):
                df = fetch_all_students()
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button("Download students.csv", csv, file_name="students.csv")

            st.markdown("**End of staff dashboard**")
