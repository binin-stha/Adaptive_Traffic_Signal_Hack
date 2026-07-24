"""Global theme — traffic-operations control room identity."""

THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@500;600;700&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap');

:root {
    --bg:        #080B11;
    --surface:   #0F141C;
    --surface-2: #141B25;
    --border:    #1E2733;
    --border-2:  #2C3542;
    --text:      #E8EDF2;
    --muted:     #8A97A8;
    --faint:     #5C6878;
    --steel:     #5AC8FA;
    --red:       #FF453A;
    --amber:     #FFD60A;
    --green:     #30D158;
}

html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', sans-serif;
    color: var(--text);
}

.stApp {
    background:
        radial-gradient(1200px 600px at 80% -10%, rgba(90,200,250,0.05), transparent 60%),
        radial-gradient(900px 500px at -10% 110%, rgba(48,209,88,0.04), transparent 55%),
        linear-gradient(180deg, #080B11 0%, #06090E 100%);
    background-attachment: fixed;
}

/* hide Streamlit chrome */
#MainMenu, footer, [data-testid="stHeader"], [data-testid="stDecoration"] {
    visibility: hidden; height: 0;
}
.block-container { padding-top: 1.4rem; padding-bottom: 2rem; max-width: 1500px; }

h1,h2,h3,h4,h5 {
    font-family: 'Chakra Petch', sans-serif !important;
    color: var(--text) !important; letter-spacing: 0.02em;
}
p, span, div, label { color: var(--text); }
small, [data-testid="stCaptionContainer"] { color: var(--muted) !important; }

/* buttons */
.stButton > button {
    font-family: 'Chakra Petch', sans-serif; font-weight: 600;
    letter-spacing: 0.06em; text-transform: uppercase; font-size: 12px;
    background: var(--surface-2); color: var(--text);
    border: 1px solid var(--border-2); border-radius: 9px;
    padding: 9px 18px; transition: all .18s ease;
}
.stButton > button:hover { background: #1B2430; border-color: var(--steel); transform: translateY(-1px); }
.stButton > button[kind="primary"] {
    background: linear-gradient(180deg, #30D158, #1FA845); border-color: #30D158; color: #04110B;
    box-shadow: 0 4px 16px rgba(48,209,88,0.25);
}
.stButton > button[kind="primary"]:hover { box-shadow: 0 6px 22px rgba(48,209,88,0.4); }

/* segmented radios (view / mode / layout) */
[data-testid="stRadio"] > div {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 11px; padding: 4px; gap: 4px;
}
[data-testid="stRadio"] label {
    background: transparent; border-radius: 8px; padding: 7px 16px;
    font-family: 'Chakra Petch', sans-serif; font-size: 12px; letter-spacing: 0.05em;
    color: var(--muted); transition: all .15s;
}
[data-testid="stRadio"] label:hover { color: var(--text); }
[data-testid="stRadio"] label[data-checked="true"],
[data-testid="stRadio"] label:has(input:checked) {
    background: var(--surface-2); color: var(--text);
    box-shadow: inset 0 0 0 1px var(--border-2);
}
[data-testid="stRadio"] label > div:first-child { display: none; }

/* inputs */
.stSelectbox > div > div, .stTextInput input, .stNumberInput input {
    background: var(--surface-2) !important; color: var(--text) !important;
    border: 1px solid var(--border-2) !important; border-radius: 9px !important;
}

/* sliders */
.stSlider [data-baseweb="slider"] > div > div { background: var(--steel); }
.stSlider div[role="slider"] {
    background: var(--text); border: 2px solid var(--steel);
    box-shadow: 0 2px 8px rgba(0,0,0,0.5);
}

/* bordered containers = docks */
[data-testid="stVerticalBlockBorderWrapper"] {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 14px !important;
    box-shadow: 0 8px 28px rgba(0,0,0,0.35);
}

/* metrics */
[data-testid="stMetric"] {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 12px; padding: 14px 16px;
}
[data-testid="stMetricLabel"] { color: var(--faint) !important;
    font-family: 'IBM Plex Mono', monospace; font-size: 10px;
    text-transform: uppercase; letter-spacing: 0.14em; }
[data-testid="stMetricValue"] { color: var(--text) !important;
    font-family: 'IBM Plex Mono', monospace; }

/* progress */
.stProgress > div > div > div {
    background: linear-gradient(90deg, var(--steel), #30D158) !important;
    border-radius: 99px;
}
.stProgress > div { background: var(--surface-2) !important; border-radius: 99px; height: 8px; }

/* images in docks */
[data-testid="stImage"] img { border-radius: 10px; border: 1px solid var(--border); }

/* expander */
[data-testid="stExpander"] {
    background: var(--surface-2); border: 1px solid var(--border); border-radius: 10px;
}

/* scrollbar */
::-webkit-scrollbar { width: 9px; height: 9px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border-2); border-radius: 99px; }
::-webkit-scrollbar-thumb:hover { background: #3A4655; }

hr { border: none; border-top: 1px solid var(--border); }
</style>
"""