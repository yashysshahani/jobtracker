import streamlit as st
from db import init_db, seed_sample_row, list_applications_df, add_application,\
      update_status, delete_application, get_connection, delete_all_apps,\
      init_id_counter_if_missing, get_next_id, bump_next_id
from audio import play_success
from analytics import count_apps_this_week, weekly_applications, get_status_count, top_companies, calendar_counts, calendar_month_ticks, top_role_terms
import pandas as pd
import plotly.express as px
import numpy as np
import datetime as dt
import altair as alt
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader

init_db()
#seed_sample_row()

# login feature:
config = st.secrets.get("auth_config")  # may be None
if not config:
    st.info("Login not configured (missing `auth_config` in secrets). Running without auth.")
else:
    authenticator = stauth.Authenticate(
        config["credentials"],
        config["cookie"]["name"],
        config["cookie"]["key"],
        config["cookie"]["expiry_days"],
    )
    name, auth_status, username = authenticator.login("Login", "main")
    if auth_status is False:
        st.error("Username/password is incorrect"); st.stop()
    elif auth_status is None:
        st.info("Please log in"); st.stop()
    authenticator.logout("Logout", "sidebar")
    st.sidebar.write(f"Hi, {name}")

authenticator.logout("Logout", "sidebar")
st.sidebar.write(f"Hi, {name}")

st.set_page_config(page_title="TrackJob", layout="wide")
st.title("Track and log your job apps")

tab_apps, tab_analytics = st.tabs(["Applications", "Analytics"])

def render_add_application_form():
    """
    Renders an application form with inputs for company, role, date, and status.
    Submitting this application form adds the application to the job application database.
    """
    with st.form("add_form"):
        company = st.text_input("Company")
        role = st.text_input("Role")
        date = st.date_input("Date applied")
        status = st.selectbox("Status", ["Applied", "OA", "Interview", "Offer", "Rejected"])
        
        submitted = st.form_submit_button("Add Application!")

    if submitted:
        try:
            new_id = get_next_id()
            bump_next_id()
            add_application(company, role, date, status)
        except Exception as e:
            st.error(str(e))

        st.session_state["just_added"] = True
        maybe_play_submit_sound(company, role)


def maybe_play_submit_sound(company: str, role: str):
    """
    If an application is added, this function will play a satisfying sound.
    """
    if st.session_state.get("just_added") is True:
        play_success()

        st.success(f"Added {company} - {role}")
        st.session_state["just_added"] = False

def read_uploaded_csv(file):
    """
    Reads a specified csv file
    """

    tries = ["utf-8", "utf-8-sig", "cp1252", "latin1"]

    for enc in tries:
        try:
            file.seek(0)
            return pd.read_csv(file, encoding=enc, sep=None, engine="python")
        
        except UnicodeDecodeError:
            continue

    file.seek(0)
    return pd.read_csv(file, encoding="latin1", sep=None, engine="python")

def app_ly_user_mapping(df_raw: pd.DataFrame, user_choice: dict[str,str]):
    """
    Input:
    - df_raw: raw dataframe representing csv uploaded by user
    - user_choice: dictionary where keys are columns in the dataframe from the site and values are the user inputted columns
    
    Given this input, the function will map the user-selected columns to the columns of the raw dataframe

    Output:
    A dataframe where columns are specified by the user
    """
    aliases = {"submitted": "Applied",
               "online assessment": "OA",
                "assessment": "OA",
                "phone screen": "Interview",
                "onsite": "Interview",
                "offer accepted": "Offer",
                "declined": "Rejected"}
    
    allowed = {"Applied", "OA", "Interview", "Offer", "Rejected"}

    picks = [user_choice['company'], user_choice['role'], user_choice['date_applied'], user_choice['status']]

    if len(set(picks)) < 4:
        st.write("Each target field must map to a different CSV column")
    
    missing = [c for c in picks if c not in df_raw.columns]
    if missing:
        raise KeyError(f"Selected column(s) not found in CSV: {missing}")
    
    out = pd.DataFrame({
        "company": df_raw[user_choice['company']].astype(str).str.strip(),
        "role": df_raw[user_choice["role"]].astype(str).str.strip(),
        "date_applied": df_raw[user_choice['date_applied']],
        "status": df_raw[user_choice["status"]].astype(str).str.strip()
    })

    s = out["status"].astype(str).str.strip().str.lower()
    s = s.map(lambda v: aliases.get(v, v))
    s = s.map(lambda v: "OA" if v == 'oa' else v.title())
    out["status"] = s

    unknown = out.loc[~out["status"].isin(allowed), "status"].unique().tolist()
    if unknown:
        st.write(f"unknown statusL {unknown}")


    return out

def prepare_rows_for_insert(valid_df):
    ret_list = []
    dates = pd.to_datetime(valid_df["date_applied"], errors='coerce').dt.date
    for i, row in enumerate(valid_df.itertuples(index=False)):
        date_iso = dates.iat[i].isoformat()
        ret_list.append((row.company, row.role, date_iso, row.status))
    
    return ret_list

def bulk_insert_applications(rows):
    if rows is None or rows == []:
        return 0
    
    sql = """
        INSERT INTO applications (company, role, date_applied, status)
        VALUES (?, ?, ?, ?)"""
    
    with get_connection() as conn:
        conn.executemany(sql, rows)

    inserted = len(rows)

    return inserted

with tab_apps:
    with st.expander("Add an application", expanded=True):
        render_add_application_form()

@st.dialog("Preview File")
def process_csv(csv):
    if csv is None:
        return
    
    csv.seek(0)

    if 'import_df_raw' in st.session_state:
        df_raw = st.session_state["import_df_raw"]

    else:
        df_raw = read_uploaded_csv(csv)
        st.session_state["import_df_raw"] = df_raw

    st.dataframe(df_raw[:10])

    columns = df_raw.columns
    company = st.selectbox(label = "Select the column that matches 'Company'", options=columns)
    role = st.selectbox(label="Select the column that matches 'Role'", options=columns)
    date_applied = st.selectbox(label="Select the column that matches 'Date Applied'", options=columns)
    status = st.selectbox(label="Select the column that matches 'Status'", options=columns)

    mapping = {"company": company,
               "role": role,
               "date_applied": date_applied,
               "status": status}
    
    valid_df = apply_user_mapping(df_raw, mapping)
    rows = prepare_rows_for_insert(valid_df)
    bulk_insert_applications(rows)
    st.rerun()

@st.dialog("Are you sure you want to delete all applications? This action is permanent")
def delete_all():
    col1, col2 = st.columns(2)
    with col1:
        yes_button = st.button("Yes")
    with col2:
        no_button = st.button("No")
    
    if yes_button:
        delete_all_apps()
        st.rerun()
    elif no_button:
        st.rerun()
        return

 
# Filtering widgets:
with st.sidebar:
    file = st.file_uploader("Import CSV", type=['csv'])
    if file:
        confirm_file = st.button("Confirm File")
    if file and confirm_file:
        st.session_state["csv"] = file
        st.session_state.pop("import_df_raw", None)
        process_csv(file)

    company_filter = st.text_input("Company contains")

    role_filter = st.text_input("Role contains")

    date_filter = st.checkbox("Enable date filter?")
    start_date = st.date_input("Start date", value=None)
    end_date = st.date_input("End date", value=None)

    status_filter = st.selectbox(
        "Filter by status",
        options=["All", "Applied", "OA", "Interview", "Offer", "Rejected"]
    )
    
    if status_filter == "All":
        status_filter = None

    limit = st.number_input("Max rows", min_value=10, value=1000, step=100)

    delete_all_button = st.button(f":red[Delete all applications?]")
    if delete_all_button:
        delete_all()

with tab_apps:
    # Data table:
    if not date_filter:
        start_date = None
        end_date = None

    if limit:
        rows = list_applications_df(limit=limit, status=status_filter, date_start=start_date, date_end=end_date, company_substr=company_filter)

    else:
        rows = list_applications_df(limit=None, status=status_filter, date_start=start_date, date_end=end_date, company_substr=company_filter)
    try:

        rows["date_applied"] = pd.to_datetime(rows["date_applied"], errors="coerce").dt.strftime("%m/%d/%Y")
        rows = rows.sort_values(["date_applied", "id"], ascending=[False, False], kind="mergesort")
        rows = rows.reindex(columns=['id', 'company', "role", "date_applied", "status"])
        rows["delete"] = False


        rows["delete"] = False
        if "apps_orig" not in st.session_state:
            st.session_state["apps_orig"] = rows.copy(deep=True)

        st.subheader("Recent applications")

        df_edit = st.data_editor(rows, hide_index=True, 
                    column_config={
                        "status": st.column_config.SelectboxColumn(
                            "Status",
                            help="Status of your application",
                            options=[
                                "Applied",
                                "OA",
                                "Interview",
                                "Offer",
                                "Rejected"
                            ]
                        ),
                        "id": None,
                        "company": "Company",
                        "role": "Role",
                        "date_applied": "Date Applied",
                        "delete": st.column_config.CheckboxColumn(
                            "Delete?",
                        )
                    },
                    disabled=["id", "company", "role", "date_applied"])
        
        export_df = df_edit.drop(columns=["delete"], errors="ignore")


        st.download_button(
            label="Download current view (CSV)",
            data=export_df.to_csv(index=False).encode("utf-8"),
            file_name="applications_current.csv",
            mime="text/csv",
            disabled=export_df.empty,
        )
        
        init_id_counter_if_missing(df_edit)

    except KeyError:
        st.write("Add your first job!")
        



    

    def apply_changes(df_edit):

        if df_edit is None or df_edit.empty or "id" not in df_edit.columns:
            return
        if "apps_orig" not in st.session_state:
            return

        orig = st.session_state["apps_orig"]
        if orig is None or orig.empty or "id" not in orig.columns:
            return

        orig_idx = orig.set_index("id")
        edit_idx = df_edit.set_index("id")
        common_ids = orig_idx.index.intersection(edit_idx.index)

        orig_status = orig_idx.loc[common_ids, "status"].astype(str).str.lower()
        edit_status = edit_idx.loc[common_ids, "status"].astype(str).str.lower()

        changed_mask = orig_status.ne(edit_status)
        changed_ids = list(common_ids[changed_mask])

        for app_id in changed_ids:
            new_status = edit_idx.at[app_id, "status"]
            update_status(app_id, new_status)

        delete_mask = edit_idx.loc[common_ids, "delete"] == True
        delete_ids = edit_idx.index[edit_idx["delete"].fillna(False).astype(bool)].tolist()

        for app_id in delete_ids:
            try:
                delete_application(app_id)
            except Exception as e:
                st.error(f"Error applying changes: {e}")

        return

with tab_apps:
    if st.button("Apply changes"):
        apply_changes(df_edit)
        st.session_state.pop("apps_orig", None)
        st.rerun()




with tab_analytics:
    st.header("Analytics")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        sql = """
            SELECT COUNT(*)
            FROM applications"""
        
        with get_connection() as conn:
            count = conn.execute(sql).fetchone()
            st.subheader(f"Total apps: :blue[{count[0]}]")

    with col2:
        st.subheader(f"Past 7 days: :blue[{count_apps_this_week()}]")

    with col3:
        applied = get_status_count("Applied")
        st.subheader(f"Applied: :green[{applied}]")

    with col4:
        rejected = get_status_count("Rejected")
        st.subheader(f"Rejected: :red[{rejected}]")


    #st.dataframe(weekly_applications(df_edit))

    
    col1, col2 = st.columns(2)

    # Weekly chart
    try:
        weekly_apps = weekly_applications(df_edit)

        with col1:
            with st.container(border=True):
                st.subheader("Weekly volume")
                st.line_chart(data=weekly_apps, x="week_start")


            with st.container(border=True):
                st.subheader("Top roles applied to")
                all_rows = list_applications_df(limit=10000)
                top_terms = top_role_terms(all_rows, n=25, ngram_range=(2, 3))

                plot = st.altair_chart(
                alt.Chart(top_terms).mark_bar().encode(
                    x=alt.X('term:N', sort=top_terms['term'].tolist()),
                    y='count:Q'
                ),
                use_container_width=True
            )

        # Heatmap
        n_days = 175
        today = pd.Timestamp.today().normalize()
        start = today - pd.Timedelta(days=n_days - 1)

        all_rows = list_applications_df(
            limit=10000,
            date_start=start.date(),
            date_end=today.date()
        )

        cal_counts = calendar_counts(all_rows, n_days)

        mat = cal_counts.pivot(index="dow", columns="week_idx", values="n").fillna(0)

        fig = px.imshow(mat, origin="upper", aspect="equal", labels=dict(color="Apps/day"), color_continuous_scale='speed')
        fig.update_yaxes(tickmode="array", tickvals=[0, 1, 2, 3, 4, 5, 6],
                        ticktext=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])


        date_mat = cal_counts.pivot(index="dow", columns="week_idx", values="date")
        date_mat = date_mat.astype(str)

        fig.update_traces(
            customdata=date_mat.values,
            hovertemplate="%{customdata}<br>Apps: %{z}<extra></extra>",
            showlegend=False
        )

        tickvals, ticktext = calendar_month_ticks(cal_counts)
        fig.update_xaxes(tickmode="array", tickvals=tickvals, ticktext=ticktext)
        fig.layout.coloraxis.showscale = False

        with col2:
            with st.container(border=True):
                st.subheader("Calendar")
                st.plotly_chart(fig)

            
            with st.container(border=True):
                st.subheader("Top companies applied to")
                top_comp = top_companies(df_edit, 15)
                top_comp = top_comp.sort_values(by="Apps", ascending=False)

                plot = st.altair_chart(
                    alt.Chart(top_comp).mark_bar().encode(
                    x=alt.X('Company:N', sort=top_comp['Apps'].tolist()),
                    y='Apps:Q'
                ),
                use_container_width=True
            )

    except NameError or KeyError:
        st.write("Add a job to view analytics")





    
    

