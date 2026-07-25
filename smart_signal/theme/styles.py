"""Art Deco (Great Gatsby) design system + control-room component styles."""

THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Josefin+Sans:wght@300;400;600&family=Marcellus&display=swap');

/* Base — obsidian black & champagne cream */
.stApp {
    background-color: #0A0A0A;
    background-image:
        repeating-linear-gradient(45deg, rgba(212,175,55,0.03) 0, rgba(212,175,55,0.03) 1px, transparent 1px, transparent 10px),
        repeating-linear-gradient(-45deg, rgba(212,175,55,0.03) 0, rgba(212,175,55,0.03) 1px, transparent 1px, transparent 10px);
    color: #F2F0E4;
    font-family: 'Josefin Sans', sans-serif;
}

header, #MainMenu, footer, [data-testid="stHeader"], [data-testid="stDecoration"] {
    visibility: hidden;
}
.block-container { padding-top: 1.2rem; max-width: 1500px; }

/* Typography */
h1, h2, h3, h4, h5, h6 {
    font-family: 'Marcellus', serif !important;
    color: #D4AF37 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.18em !important;
}
p, span, div, label { font-family: 'Josefin Sans', sans-serif; color: #F2F0E4; }
small, [data-testid="stCaptionContainer"] {
    color: #888888 !important; text-transform: uppercase; letter-spacing: 0.1em;
}

/* Inputs — underlined elegance */
.stTextInput input, .stSelectbox div[data-baseweb="select"], .stNumberInput input {
    background-color: transparent !important;
    border: none !important;
    border-bottom: 2px solid #D4AF37 !important;
    border-radius: 0px !important;
    color: #F2F0E4 !important;
    font-family: 'Josefin Sans', sans-serif !important;
    box-shadow: none !important;
    transition: all 0.3s ease;
}
.stTextInput input:focus, .stSelectbox div[data-baseweb="select"]:focus-within {
    border-bottom: 2px solid #F2E8C4 !important;
    box-shadow: 0 4px 10px rgba(212,175,55,0.2) !important;
}

/* Buttons — precision instruments */
.stButton > button {
    background-color: transparent !important;
    border: 1px solid #D4AF37 !important;
    color: #D4AF37 !important;
    border-radius: 0px !important;
    font-family: 'Marcellus', serif !important;
    text-transform: uppercase !important;
    letter-spacing: 0.15em !important;
    padding: 0.5rem 1.4rem !important;
    transition: all 0.4s ease;
}
.stButton > button:hover {
    background-color: #D4AF37 !important;
    color: #0A0A0A !important;
    box-shadow: 0 0 15px rgba(212,175,55,0.4) !important;
    transform: translateY(-2px);
}
.stButton > button[kind="primary"] {
    background-color: #D4AF37 !important; color: #0A0A0A !important;
}
.stButton > button[kind="primary"]:hover {
    background-color: #F2E8C4 !important;
    box-shadow: 0 0 18px rgba(212,175,55,0.55) !important;
}

/* Radios (view / mode / dock selectors) */
[data-testid="stRadio"] label { color: #F2F0E4 !important; }
[data-testid="stRadio"] label[data-checked="true"],
[data-testid="stRadio"] label:has(input:checked) { color: #D4AF37 !important; }

/* Bordered containers = deco cards */
[data-testid="stVerticalBlockBorderWrapper"] {
    background-color: #141414 !important;
    border: 1px solid rgba(212,175,55,0.3) !important;
    border-radius: 0px !important;
    transition: all 0.4s ease;
}
[data-testid="stVerticalBlockBorderWrapper"]:hover {
    border: 1px solid rgba(212,175,55,1) !important;
    box-shadow: 0 10px 30px rgba(0,0,0,0.8), 0 0 15px rgba(212,175,55,0.1);
}

/* Progress */
.stProgress > div > div > div {
    background: linear-gradient(90deg, #D4AF37, #F2E8C4) !important; border-radius: 0;
}
.stProgress > div { background: #1A1A1A !important; border-radius: 0; height: 8px; }

/* Dividers — Art Deco double rule */
hr { border: none !important; border-top: 2px double rgba(212,175,55,0.4) !important; margin: 2rem 0 !important; }

/* Checkboxes */
.stCheckbox span[data-baseweb="checkbox"] div {
    border-radius: 0px !important; border: 1px solid #D4AF37 !important;
    background-color: transparent !important;
}
.stCheckbox span[data-baseweb="checkbox"] div[aria-checked="true"] {
    background-color: #D4AF37 !important;
}

/* Scrollbar */
::-webkit-scrollbar { width: 9px; height: 9px; }
::-webkit-scrollbar-track { background: #0A0A0A; }
::-webkit-scrollbar-thumb { background: rgba(212,175,55,0.4); }
::-webkit-scrollbar-thumb:hover { background: rgba(212,175,55,0.7); }
</style>
"""
DASHBOARD_CSS = """
<style>
/* ── Control-room component classes (Art Deco) ── */

/* decision rail — the one class nothing else defines */
.ss-rail { height:calc(100vh - 150px); overflow-y:auto; padding-right:4px; }

/* camera docks (base; live docks add inline overrides) */
.ss-dock { position:relative; border-radius:0px; overflow:hidden;
    border:2px solid #D4AF37; background:#000;
    box-shadow:0 0 14px rgba(212,175,55,0.12); }
.ss-dock img { width:100%; height:100%; object-fit:cover; display:block; }
.ss-nofeed { position:absolute; inset:0; display:flex; align-items:center; justify-content:center;
    color:#D4AF37; font-family:'Marcellus',serif; font-size:13px; letter-spacing:.18em; }
.ss-osd-top { position:absolute; top:0; left:0; right:0; display:flex; align-items:center; gap:10px;
    padding:8px 12px; background:linear-gradient(180deg, rgba(10,10,10,.9), rgba(10,10,10,0)); }
.ss-osd-bot { position:absolute; bottom:0; left:0; right:0; display:flex;
    justify-content:space-between; align-items:center; padding:8px 12px;
    background:linear-gradient(0deg, rgba(10,10,10,.9), rgba(10,10,10,0));
    font-family:'Josefin Sans',sans-serif; font-size:11px; color:#F2F0E4; }
.ss-dir { font-family:'Marcellus',serif; font-size:13px; letter-spacing:.15em; color:#D4AF37; flex:1; }
.ss-osd-counts { font-family:'Josefin Sans',sans-serif; font-size:11px; color:#888888; }

/* decision cards (base; control room refines these further) */
.ss-card { background:#141414; border:1px solid rgba(212,175,55,0.3); border-radius:0px;
    padding:16px; margin-bottom:16px; }
.ss-card-active { border-left:3px solid #D4AF37; }
.ss-card-title { font-family:'Marcellus',serif; font-size:13px; letter-spacing:.15em;
    text-transform:uppercase; color:#D4AF37; margin-bottom:10px; }
.ss-idle { color:#5C5C5C; font-size:12px; font-family:'Josefin Sans',sans-serif;
    text-align:center; padding:14px 0; letter-spacing:.08em; }
.ss-chain { font-size:12px; color:#888888; padding:3px 0; }
.ss-chain-k { color:#5C5C5C; }
.ss-log { font-size:11px; padding:4px 0; border-bottom:1px solid rgba(212,175,55,0.12); }
.ss-rules { font-family:'Josefin Sans',sans-serif; font-size:11px; color:#D4AF37; letter-spacing:.06em; }

/* tighten the room so it fits the viewport */
.block-container { padding-top:0.8rem !important; }
[data-testid="stHorizontalBlock"] { gap:0.6rem !important; }
</style>
"""