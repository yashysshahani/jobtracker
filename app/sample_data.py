import pandas as pd
from datetime import date, timedelta
import random

random.seed(7)

companies = [
    "Intuitive Surgical", "Notion", "eBay", "Cisco", "Western Digital",
    "Google", "Microsoft", "NVIDIA", "Meta", "Amazon",
    "Databricks", "Snowflake", "DoorDash", "Airbnb", "LinkedIn",
    "Stripe", "Square", "OpenAI", "Uber", "Lyft"
]

roles = [
    "Data Scientist Intern", "Machine Learning Engineer Intern",
    "Software Engineer", "Software Engineer Intern",
    "Data Analyst", "Business Analyst",
    "Applied Scientist Intern", "People Analytics Intern",
    "Research Scientist Intern", "Analytics Engineer Intern",
    "Backend Engineer", "Frontend Engineer", "Full Stack Engineer",
    "Business Intelligence Analyst", "Quant Research Intern"
]

# Allowed plus synonyms user mapping handles
status_pool = [
    "Applied", "OA", "Interview", "Offer", "Rejected",
    "submitted", "online assessment", "assessment",
    "phone screen", "onsite", "offer accepted", "declined"
]

today = date.today()
rows = []
num_rows = 48  # ~7 weeks worth

for i in range(num_rows):
    d = today - timedelta(days=random.randint(0, 60))
    rows.append({
        "company": random.choice(companies),
        "role": random.choice(roles),
        "date_applied": d.isoformat(),
        "status": random.choice(status_pool)
    })

df = pd.DataFrame(rows).sort_values("date_applied").reset_index(drop=True)

path = "/mnt/data/sample_applications.csv"
df.to_csv(path, index=False)

import caas_jupyter_tools as cj
cj.display_dataframe_to_user("Sample applications CSV (preview)", df.head(20))

