"""Art Deco 'champagne' design system + control-room component styles (light)."""

THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Josefin+Sans:wght@300;400;600&family=Marcellus&display=swap');

/* Base — champagne plaster with a faint deco crosshatch */
.stApp {
    background-color: #ECE4D2;
    background-image:
        repeating-linear-gradient(45deg, rgba(154,123,30,0.05) 0, rgba(154,123,30,0.05) 1px, transparent 1px, transparent 12px),
        repeating-linear-gradient(-45deg, rgba(154,123,30,0.05) 0, rgba(154,123,30,0.05) 1px, transparent 1px, transparent 12px);
    color: #2A2314;
    font-family: 'Josefin Sans', sans-serif;
}

header, #MainMenu, footer, [data-testid="stHeader"], [data-testid="stDecoration"] {
    visibility: hidden;
}
.block-container { padding-top: 1.2rem; max-width: 1500px; }

/* Typography */
h1, h2, h3, h4, h5, h6 {
    font-family: 'Marcellus', serif !important;
    color: #9A7B1E !important;
    text-transform: uppercase !important;
    letter-spacing: 0.18em !important;
}
p, span, div, label { font-family: 'Josefin Sans', sans-serif; color: #2A2314; }
small, [data-testid="stCaptionContainer"] {
    color: #6E6248 !important; text-transform: uppercase; letter-spacing: 0.1em;
}

/* Inputs — underlined elegance */
.stTextInput input, .stSelectbox div[data-baseweb="select"], .stNumberInput input {
    background-color: transparent !important;
    border: none !important;
    border-bottom: 2px solid #9A7B1E !important;
    border-radius: 0px !important;
    color: #2A2314 !important;
    font-family: 'Josefin Sans', sans-serif !important;
    box-shadow: none !important;
    transition: all 0.3s ease;
}
.stTextInput input:focus, .stSelectbox div[data-baseweb="select"]:focus-within {
    border-bottom: 2px solid #C9A227 !important;
    box-shadow: 0 4px 10px rgba(154,123,30,0.18) !important;
}

/* Buttons */
.stButton > button {
    background-color: transparent !important;
    border: 1px solid #9A7B1E !important;
    color: #9A7B1E !important;
    border-radius: 0px !important;
    font-family: 'Marcellus', serif !important;
    text-transform: uppercase !important;
    letter-spacing: 0.15em !important;
    padding: 0.5rem 1.4rem !important;
    transition: all 0.4s ease;
}
.stButton > button:hover {
    background-color: #C9A227 !important;
    color: #2A2314 !important;
    box-shadow: 0 0 15px rgba(201,162,39,0.35) !important;
    transform: translateY(-2px);
}
.stButton > button[kind="primary"] {
    background-color: #9A7B1E !important; color: #FAF6EB !important;
}
.stButton > button[kind="primary"]:hover {
    background-color: #C9A227 !important; color: #2A2314 !important;
    box-shadow: 0 0 18px rgba(201,162,39,0.5) !important;
}

/* Radios */
[data-testid="stRadio"] label { color: #2A2314 !important; }
[data-testid="stRadio"] label[data-checked="true"],
[data-testid="stRadio"] label:has(input:checked) { color: #9A7B1E !important; }

/* Bordered containers = deco cards */
[data-testid="stVerticalBlockBorderWrapper"] {
    background-color: #FAF6EB !important;
    border: 2px solid rgba(154,123,30,0.65) !important;
    border-radius: 0px !important;
    transition: border-color 0.35s ease, box-shadow 0.35s ease, transform 0.35s ease;
}
[data-testid="stVerticalBlockBorderWrapper"]:hover {
    border-color: #9A7B1E !important;
    box-shadow: 0 8px 24px rgba(42,35,20,0.12), 0 0 0 1px rgba(201,162,39,0.35) !important;
    transform: translateY(-2px);
}

/* Progress */
.stProgress > div > div > div {
    background: linear-gradient(90deg, #9A7B1E, #C9A227) !important; border-radius: 0;
}
.stProgress > div { background: #E3DAC4 !important; border-radius: 0; height: 8px; }

/* Dividers — double rule */
hr { border: none !important; border-top: 2px double rgba(154,123,30,0.4) !important; margin: 2rem 0 !important; }

/* Checkboxes */
.stCheckbox span[data-baseweb="checkbox"] div {
    border-radius: 0px !important; border: 1px solid #9A7B1E !important;
    background-color: transparent !important;
}
.stCheckbox span[data-baseweb="checkbox"] div[aria-checked="true"] {
    background-color: #C9A227 !important;
}

/* Scrollbar */
::-webkit-scrollbar { width: 9px; height: 9px; }
::-webkit-scrollbar-track { background: #ECE4D2; }
::-webkit-scrollbar-thumb { background: rgba(154,123,30,0.45); }
::-webkit-scrollbar-thumb:hover { background: rgba(154,123,30,0.7); }
</style>
"""

DASHBOARD_CSS = """
<style>
/* decision rail */
.ss-rail { height:calc(100vh - 150px); overflow-y:auto; padding-right:4px; }

/* camera docks — screens stay dark, framed in gold */
.ss-dock { position:relative; border-radius:0px; overflow:hidden;
    border:2px solid #9A7B1E; background:#0A0A0A;
    box-shadow:0 0 14px rgba(154,123,30,0.18); }
.ss-dock img { width:100%; height:100%; object-fit:cover; display:block; }
.ss-nofeed { position:absolute; inset:0; display:flex; align-items:center; justify-content:center;
    color:#C9A227; font-family:'Marcellus',serif; font-size:13px; letter-spacing:.18em; }
.ss-osd-top { position:absolute; top:0; left:0; right:0; display:flex; align-items:center; gap:10px;
    padding:8px 12px; background:linear-gradient(180deg, rgba(10,10,10,.9), rgba(10,10,10,0)); }
.ss-osd-bot { position:absolute; bottom:0; left:0; right:0; display:flex;
    justify-content:space-between; align-items:center; padding:8px 12px;
    background:linear-gradient(0deg, rgba(10,10,10,.9), rgba(10,10,10,0));
    font-family:'Josefin Sans',sans-serif; font-size:11px; color:#F2EFE4; }
.ss-dir { font-family:'Marcellus',serif; font-size:13px; letter-spacing:.15em; color:#C9A227; flex:1; }
.ss-osd-counts { font-family:'Josefin Sans',sans-serif; font-size:11px; color:#B8AC92; }

/* decision cards — ivory */
.ss-card { background:#FAF6EB; border:1px solid rgba(154,123,30,0.30); border-radius:0px;
    padding:16px; margin-bottom:16px; }
.ss-card-active { border-left:3px solid #9A7B1E; }
.ss-card-title { font-family:'Marcellus',serif; font-size:13px; letter-spacing:.15em;
    text-transform:uppercase; color:#9A7B1E; margin-bottom:10px; }
.ss-idle { color:#A09376; font-size:12px; font-family:'Josefin Sans',sans-serif;
    text-align:center; padding:14px 0; letter-spacing:.08em; }
.ss-chain { font-size:12px; color:#6E6248; padding:3px 0; }
.ss-chain-k { color:#A09376; }
.ss-log { font-size:11px; padding:4px 0; border-bottom:1px solid rgba(154,123,30,0.15); }
.ss-rules { font-family:'Josefin Sans',sans-serif; font-size:11px; color:#9A7B1E; letter-spacing:.06em; }

.block-container { padding-top:0.8rem !important; }
[data-testid="stHorizontalBlock"] { gap:0.6rem !important; }

/* ── Readability reinforcement — no dark bleed-through on widgets ── */

/* Labels everywhere */
label, [data-testid="stWidgetLabel"],
.stTextInput label, .stSelectbox label, .stCheckbox label,
.stSlider label, .stNumberInput label, .stRadio label {
    color: #2A2314 !important;
}

/* Input fields & select triggers — solid ivory, espresso text */
.stTextInput input,
.stNumberInput input,
.stSelectbox div[data-baseweb="select"] {
    background-color: #FAF6EB !important;
    color: #2A2314 !important;
}
.stSelectbox div[data-baseweb="select"] span,
.stSelectbox div[data-baseweb="select"] > div {
    color: #2A2314 !important;
}

/* Dropdown options */
[data-baseweb="menu"], [data-baseweb="menu"] ul {
    background-color: #FAF6EB !important;
}
[data-baseweb="menu"] li, [data-baseweb="menu"] li div,
[data-baseweb="menu"] [role="option"] {
    background-color: #FAF6EB !important;
    color: #2A2314 !important;
}
[data-baseweb="menu"] li:hover, [data-baseweb="menu"] li:hover div,
[data-baseweb="menu"] li[aria-selected="true"] {
    background-color: #C9A227 !important;
    color: #2A2314 !important;
}

/* File uploader (upload video to direction) */
[data-testid="stFileUploader"] section,
[data-testid="stFileUploader"] [role="button"],
[data-testid="stFileUploader"] button {
    background-color: #FAF6EB !important;
    border: 1px dashed #9A7B1E !important;
    color: #2A2314 !important;
}
[data-testid="stFileUploader"] span,
[data-testid="stFileUploader"] p,
[data-testid="stFileUploader"] small {
    color: #2A2314 !important;
}

/* Download button (Export Layout) */
[data-testid="stDownloadButton"] button {
    background-color: transparent !important;
    border: 1px solid #9A7B1E !important;
    color: #9A7B1E !important;
    border-radius: 0 !important;
    font-family: 'Marcellus', serif !important;
    text-transform: uppercase !important;
    letter-spacing: 0.15em !important;
}
[data-testid="stDownloadButton"] button:hover {
    background-color: #C9A227 !important;
    color: #2A2314 !important;
}

/* Checkbox (PRIMARY FOCUS) */
.stCheckbox span[data-baseweb="checkbox"] {
    background-color: #FAF6EB !important;
    border: 1px solid #9A7B1E !important;
}
.stCheckbox label span { color: #2A2314 !important; }

/* Slider value bubble */
.stSlider [data-baseweb="popover"] {
    background-color: #FAF6EB !important;
    color: #2A2314 !important;
}
</style>
"""