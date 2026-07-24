"""
Theme module for Smart Signal — holds all CSS styling.
"""

THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

.stApp {
    background-color: #060B14;
    color: #F1F5F9;
    font-family: 'Inter', sans-serif;
}
.block-container { padding-top: 1.2rem; max-width: 1500px; }

h1,h2,h3,h4 { font-family: 'Inter', sans-serif; color: #F1F5F9; letter-spacing: -0.02em; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    gap: 2px; background: #0D1420; border-radius: 12px;
    padding: 4px; border: 1px solid #1E293B;
}
.stTabs [data-baseweb="tab"] {
    background: transparent; border: none; border-radius: 8px;
    color: #94A3B8; font-size: 13px; font-weight: 500;
    padding: 10px 22px; transition: all 0.2s;
}
.stTabs [data-baseweb="tab"]:hover { background: #1C2A3E; color: #F1F5F9; }
.stTabs [data-baseweb="tab"][aria-selected="true"] {
    background: #3B82F6; color: #fff;
}
.stTabs [data-baseweb="tab-highlight"] { display: none; }

/* Buttons */
.stButton > button {
    background: #141E2E; color: #F1F5F9; border: 1px solid #334155;
    border-radius: 8px; padding: 8px 18px; font-size: 13px;
    font-weight: 500; transition: all 0.2s;
}
.stButton > button:hover { background: #1C2A3E; border-color: #3B82F6; }
.stButton > button[kind="primary"] { background: #3B82F6; border-color: #3B82F6; color: #fff; }
.stButton > button[kind="primary"]:hover { background: #60A5FA; }

/* Metrics */
[data-testid="stMetric"] {
    background: #0D1420; border: 1px solid #1E293B;
    border-radius: 12px; padding: 16px;
}
[data-testid="stMetricLabel"] { color: #64748B; font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em; }
[data-testid="stMetricValue"] { color: #F1F5F9; font-family: 'JetBrains Mono', monospace; font-size: 24px; }

/* Inputs */
.stSelectbox > div > div, .stTextInput > div > div > input,
.stNumberInput > div > div > input {
    background: #141E2E; color: #F1F5F9; border: 1px solid #1E293B;
    border-radius: 8px; font-size: 13px;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0D1420 0%, #060B14 100%);
    border-right: 1px solid #1E293B;
}

/* Alerts */
[data-testid="stAlert"] { border-radius: 10px; }

/* Scrollbar */
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: #0D1420; }
::-webkit-scrollbar-thumb { background: #334155; border-radius: 99px; }

hr { border: none; border-top: 1px solid #1E293B; }
</style>

.stCanvas > div > div {
    background-color: transparent !important;
}
.stCanvas canvas {
    background-color: transparent !important;
}
"""