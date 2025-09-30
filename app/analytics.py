import sqlite3
from datetime import datetime, timedelta
import sqlite3
from pathlib import Path
from db import get_connection, list_applications_df
import pandas as pd
import streamlit as st
from collections import Counter
import re
from sklearn.feature_extraction.text import CountVectorizer
import numpy as np

DB_PATH = Path(__file__).parent / "job_apps.db"

STOPWORDS = {
    "intern","summer","fall","spring","2024","2025","ii","iii","sr","jr",
    "the","and","of","for","with","to","a","an","at","—","-","|","(",")"
}




# Datetime helpers
def _normalize_dates(s):
    # s is a string of dates
    # returns pandas datetime with no time
    return pd.to_datetime(s, errors='coerce').dt.normalize()

def _window_bounds(n_days: int, end=None):
    # end defaults to "today" at midnight

    end = (pd.Timestamp.today().normalize() if end is None
           else pd.to_datetime(end).normalize())
    
    start = end - pd.Timedelta(days=n_days - 1)

    return start, end

def _anchor_week_start(ts: pd.Timestamp, week_start="MON"):
    # ,pve timestamp to the start of its week
    
    ts = pd.to_datetime(ts).normalize()

    if week_start.upper() == "MON":
        return ts - pd.Timedelta(days=ts.weekday())
    
    if week_start.upper() == "SUN":
        return ts - pd.Timedelta(days=(ts.weekday() + 1) % 7)
    
    raise ValueError("week start must be MON or SUN")

def last_seven_days():
    now = datetime.now()
    dates = []

    for x in range(7):
        d = now - timedelta(days = x)
        dates.append(d.strftime("%Y-%m-%d"))

    return dates
    

def count_apps_this_week():
    days = last_seven_days()
    end = days[0]
    start = days[-1]

    sql = """
        SELECT COUNT(*) FROM applications
        WHERE date_applied >= ? AND date_applied <= ?;
        """

    with get_connection() as conn:
        num = conn.execute(sql, (start, end)).fetchone()
        return num[0]


def weekly_applications(df: pd.DataFrame, window: int=4):
    out = df[['date_applied']].copy()
    out['date_applied'] = pd.to_datetime(out['date_applied'], errors='coerce')
    out = out.dropna(subset=['date_applied'])

    out = out.set_index('date_applied').sort_index()


    weekly = out.resample('W-SUN').size().rename('apps').to_frame()
    
    weekly.index = weekly.index - pd.Timedelta(days=6)
    weekly.index.name = 'week_start'

    weekly = weekly.asfreq('W-MON', fill_value=0)

    weekly['apps_ma'] = weekly['apps'].rolling(window=window, min_periods=1).mean()

    return weekly.reset_index().rename(columns={'date_applied': 'week_start'})


def get_status_count(status: str):
    if status not in {'Applied', 'OA', 'Interview', 'Offer', 'Rejected'}:
        print("Status not available")
        return
    
    sql = """
        SELECT COUNT(*) FROM applications
        WHERE status = ?
        """

    with get_connection() as conn:
        num = conn.execute(sql, (status, )).fetchone()
        return num[0]

def apps_per_day(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return columns: ['day','n']
    """
    # ensure date_applied is datetime
    # df.assign(day=df['date_applied'].dt.floor('D')).groupby('day').size().reset_index(name='n')
    ...

def cumulative_apps(per_day_df: pd.DataFrame) -> pd.DataFrame:
    """
    Input from apps_per_day(); return ['day','cum']
    """
    # per_day_df.assign(cum=per_day_df['n'].cumsum())
    ...

def top_companies(df: pd.DataFrame, k: int = 15) -> pd.DataFrame:
    """
    Return ['company','n'] for top k.
    """
    
    top_k_companies = df.sort_values('company').head(k)

    apps_per_company = {}

    for company in df["company"]:
        if company not in apps_per_company:
            apps_per_company[company] = 1
        elif company in apps_per_company:
            apps_per_company[company] += 1

    top_k_companies = pd.DataFrame(apps_per_company.items(), columns=['Company', 'Apps'])
    top_k_companies = top_k_companies.sort_values('Apps', ascending=False).head(k)

    return top_k_companies

def pipeline_funnel(df: pd.DataFrame, order=None) -> pd.DataFrame:
    """
    Map free-form statuses into an ordered pipeline for a funnel.
    Default order: ["Applied","OA","Interview","Offer"]
    Return ['stage','n'].
    """
    ...

def weekday_by_status(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return heatmap-ready counts: ['weekday','status','n']
    """
    # weekday = df['date_applied'].dt.day_name()
    ...

def time_to_first_response(df: pd.DataFrame) -> pd.DataFrame:
    """
    If 'response_date' exists, return ['lag_days'] for histogram.
    """
    # dropna on response_date, compute (response_date - date_applied).dt.days as 'lag_days'

def calendar_counts(df: pd.DataFrame, n_days=30, date_col="date_applied"):
    dates = _normalize_dates(df[date_col]).dropna()
    start, end = _window_bounds(n_days)
    mask = (dates >= start) & (dates <= end)
    dates = dates[mask]

    day_index = pd.date_range(start, end, freq="D")
    counts = dates.value_counts().rename_axis("date").rename("n").to_frame()\
        .reindex(day_index, fill_value=0)\
            .rename_axis("date").reset_index()
    
    anchor = _anchor_week_start(start, week_start="MON")
    delta = (counts["date"] - anchor).dt.days
    dow = (delta % 7).astype(int)
    week_idx = (delta // 7).astype(int)

    counts["dow"] = dow
    counts['week_idx'] = week_idx

    return counts[["date", "n", "dow", "week_idx"]]

def calendar_month_ticks(cal_counts):
    if cal_counts is None or cal_counts.empty:
        return [], []
    s = cal_counts.assign(month=cal_counts["date"].dt.to_period("M"))
    first_week = s.groupby("month", sort=True)["week_idx"].min()
    tickvals = first_week.values.tolist()
    ticktext = [m.strftime("%b") for m in first_week.index.to_timestamp()]

    return tickvals, ticktext


def _normalize_role(text: str):
    cleaned = text.lower().strip()
    cleaned = re.sub('\W_\s*', ' ', cleaned)
    return cleaned

def top_role_terms(df, n=20, ngram_range=(1, 2)):
    roles = df['role'].astype(str).map(_normalize_role)
    v = CountVectorizer(ngram_range=ngram_range,
                        min_df=2,
                        stop_words=['summer', 'fall', 'spring', 'jr', 'sr', 'the', 'and', 'of', 'for', 'with',
                                    'to', 'a', 'an', 'job', '2025', "id", 'hybrid', 'graduate', "i", "ii", "iii", "usds", "2026",
                                    "new", "grad", "program", "internship", "intern", "staff", "co", "op"])
    
    X = v.fit_transform(roles)
    counts = np.asarray(X.sum(axis=0)).ravel()
    terms = v.get_feature_names_out()

    out = pd.DataFrame({'term': terms,
                        'count': counts})
    
    df_sorted = out.sort_values(by="count", ascending=False)
    df_sorted.index = pd.CategoricalIndex(df_sorted.index,
                                       categories=df_sorted.index,
                                       ordered=True)

    return df_sorted.head(10)




