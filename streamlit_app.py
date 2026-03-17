import streamlit as st
import requests
from io import BytesIO
import zipfile
import re
import concurrent.futures

# --- CONFIG ---
st.set_page_config(page_title="SHNGM Downloader", page_icon="📖", layout="centered")

# --- CUSTOM CSS DENGAN PALET WARNA KHUSUS ---
# #181C14 (Darkest), #3C3D37 (Dark Gray), #697565 (Muted Green), #ECDFCC (Cream)
st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

    /* Global Background & Text */
    .stApp {{
        background-color: #181C14 !important;
        color: #ECDFCC !important;
        font-family: 'Inter', sans-serif !important;
    }}

    /* Input Field */
    .stTextInput input {{
        background-color: #3C3D37 !important;
        color: #ECDFCC !important;
        border: 1px solid #697565 !important;
        border-radius: 12px !important;
        height: 48px !important;
        font-size: 16px !important;
    }}
    .stTextInput input::placeholder {{
        color: #697565 !important;
    }}

    /* Tombol Utama (Cari & Download) */
    .stButton > button {{
        background-color: #697565 !important;
        color: #ECDFCC !important;
        border-radius: 12px !important;
        border: none !important;
        font-weight: 600 !important;
        height: 48px !important;
        transition: all 0.3s ease !important;
    }}
    .stButton > button:hover {{
        background-color: #ECDFCC !important;
        color: #181C14 !important;
        transform: translateY(-2px) !important;
    }}

    /* Tombol Pilih & Hapus (Secondary) */
    .sub-btn .stButton > button {{
        height: 38px !important;
        font-size: 13px !important;
        background-color: #3C3D37 !important;
        border: 1px solid #697565 !important;
    }}

    /* Manga Card */
    .manga-card {{
        background-color: #3C3D37;
        padding: 20px;
        border-radius: 16px;
        border: 1px solid #697565;
        margin-bottom: 20px;
        color: #ECDFCC;
    }}

    /* Multiselect / Tags */
    span[data-baseweb="tag"] {{
        background-color: #697565 !important;
        color: #ECDFCC !important;
    }}
    
    /* Progress Bar */
    div[data-testid="stProgress"] > div > div > div > div {{
        background-color: #ECDFCC !important;
    }}

    /* Typography */
    h1, h2, h3, p, label {{
        color: #ECDFCC !important;
    }}

    /* Radio Button */
    div[data-testid="stRadio"] label {{
        color: #ECDFCC !important;
    }}
    </style>
    """, unsafe_allow_html=True)

# --- HELPER FUNCTIONS ---
HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://shngm.io/"}

def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name).strip().replace(" ", "_")

def extract_number(text):
    nums = re.findall(r"(\d+\.?\d*)", str(text))
    return float(nums[0]) if nums else 0

def fetch_image(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        return r.content if r.status_code == 200 else None
    except: return None

# --- UI LAYOUT ---
st.markdown("<h1 style='text-align: center;'>📖 SHNGM <span style='color: #697565;'>Downloader</span></h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; opacity: 0.8;'>Simple & Professional Manga Downloader</p>", unsafe_allow_html=True)

if 'manga_data' not in st.session_state: st.session_state.manga_data = None
if 'sel_ch' not in st.session_state: st.session_state.sel_ch = []

# --- SEARCH ---
col_in, col_sr = st.columns([3, 1])
m_id = col_in.text_input("ID Manga", placeholder="Masukkan ID Manga...", label_visibility="collapsed")

if col_sr.button("🔍 CARI", use_container_width=True):
    try:
        with st.spinner("Searching..."):
            m_res = requests.get(f"https://api.shngm.io/v1/manga/detail/{m_id}", headers=HEADERS).json()
            c_res = requests.get(f"https://api.shngm.io/v1/chapter/{m_id}/list?page=1&page_size=1500", headers=HEADERS).json()
            st.session_state.manga_data = {
                "title": m_res["data"]["title"],
                "raw_chapters": c_res["data"], 
                "map": {f"Ch {c['chapter_number']}": c["chapter_id"] for c in c_res["data"]}
            }
            st.session_state.sel_ch = []
    except:
        st.error("Gagal! ID tidak valid.")

# --- CONTENT ---
if st.session_state.manga_data:
    m = st.session_state.manga_data
    
    st.markdown(f"""
    <div class='manga-card'>
        <small style='color: #697565;'>MANGA SELECTED</small>
        <h2 style='margin:0;'>{m['title']}</h2>
    </div>
    """, unsafe_allow_html=True)

    order = st.radio("Urutan:", ["Ascending", "Descending"], horizontal=True)
    is_desc = (order == "Descending")
    
    sorted_chapters = sorted(m['raw_chapters'], key=lambda x: float(x['chapter_number']), reverse=is_desc)
    current_labels = [f"Ch {c['chapter_number']}" for c in sorted_chapters]

    st.markdown('<div class="sub-btn">', unsafe_allow_html=True)
    c1, c2, _ = st.columns([1, 1, 1])
    if c1.button("Pilih Semua"): st.session_state.sel_ch = current_labels
    if c2.button("Hapus Semua"): st.session_state.sel_ch = []
    st.markdown('</div>', unsafe_allow_html=True)

    selected = st.multiselect("Daftar Chapter:", current_labels, key="sel_ch")

    # --- PROCESS ---
    if st.button("🚀 MULAI DOWNLOAD (.CBZ)", use_container_width=True):
        if not selected:
            st.warning("Pilih chapter!")
        else:
            main_zip = BytesIO()
            sorted_sel = sorted(selected, key=extract_number)
            
            pbar = st.progress(0)
            st_text = st.empty()

            try:
                with zipfile.ZipFile(main_zip, "w") as m_zip:
                    for i, label in enumerate(sorted_sel):
                        st_text.markdown(f"⏳ **Processing:** `{label}`")
                        ch_id = m['map'][label]
                        
                        res = requests.get(f"https://api.shngm.io/v1/chapter/detail/{ch_id}", headers=HEADERS).json()["data"]
                        urls = [res["base_url"] + res["chapter"]["path"] + img for img in res["chapter"]["data"]]

                        with concurrent.futures.ThreadPoolExecutor(max_workers=15) as ex:
                            imgs = list(ex.map(fetch_image, urls))

                        cbz_buf = BytesIO()
                        with zipfile.ZipFile(cbz_buf, "w") as c_zip:
                            for idx, img in enumerate(imgs):
                                if img: c_zip.writestr(f"{idx+1:03d}.jpg", img)
                        
                        m_zip.writestr(f"{sanitize_filename(label)}.cbz", cbz_buf.getvalue())
                        pbar.progress((i + 1) / len(sorted_sel))
                
                st_text.success(f"✅ Selesai memproses {len(sorted_sel)} Chapter!")
                
                # POPUP DOWNLOAD INSTAN (Fast Output)
                zip_ready = main_zip.getvalue()
                st.download_button(
                    label="📥 SIMPAN FILE ZIP",
                    data=zip_ready,
                    file_name=f"{sanitize_filename(m['title'])}.zip",
                    mime="application/zip",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"Error: {e}")

st.markdown("<br><p style='text-align: center; color: #697565; font-size: 12px;'>SHNGM Downloader Tool</p>", unsafe_allow_html=True)
