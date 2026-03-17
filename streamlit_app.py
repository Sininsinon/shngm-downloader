import streamlit as st
import requests
from io import BytesIO
import zipfile
import re
import concurrent.futures

# --- CONFIG ---
st.set_page_config(page_title="SHNGM Downloader", page_icon="📖", layout="centered")

# --- MODERN STYLING (UI/UX) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

    html, body, [class*="st-"] {
        font-family: 'Inter', sans-serif !important;
        font-size: 15px;
    }

    /* Background & Card Style */
    .main {
        background-color: #f8f9fa;
    }
    
    .stTextInput input {
        border-radius: 10px !important;
        border: 1px solid #d1d5db !important;
        padding: 12px !important;
        font-size: 16px !important;
    }

    /* Modern Button Styling */
    .stButton > button {
        border-radius: 10px !important;
        font-weight: 600 !important;
        transition: all 0.3s ease !important;
        border: none !important;
        height: 48px !important;
    }

    /* Tombol Cari (Blue Accent) */
    div[data-testid="column"] .stButton > button {
        background-color: #4F46E5 !important;
        color: white !important;
    }

    /* Tombol Pilih & Hapus Semua (Outline Style) */
    .sub-btn .stButton > button {
        height: 35px !important;
        font-size: 13px !important;
        background-color: transparent !important;
        color: #4F46E5 !important;
        border: 1px solid #4F46E5 !important;
    }
    
    .sub-btn .stButton > button:hover {
        background-color: #4F46E5 !important;
        color: white !important;
    }

    /* Download Button (Success Green) */
    .stDownloadButton > button {
        background: linear-gradient(135deg, #10B981 0%, #059669 100%) !important;
        color: white !important;
        box-shadow: 0 4px 15px rgba(16, 185, 129, 0.3) !important;
        width: 100% !important;
        height: 55px !important;
        font-size: 17px !important;
    }

    /* Container Box */
    .manga-card {
        background-color: white;
        padding: 20px;
        border-radius: 15px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        margin-bottom: 20px;
    }

    /* Progress Bar */
    .stProgress > div > div > div > div {
        background-color: #4F46E5 !important;
    }
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
st.markdown("<h1 style='text-align: center; color: #1F2937;'>📖 SHNGM <span style='color: #4F46E5;'>Downloader</span></h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #6B7280; margin-top: -15px;'>Download manga favoritmu dalam format .CBZ dengan cepat</p>", unsafe_allow_html=True)

if 'manga_data' not in st.session_state: st.session_state.manga_data = None
if 'sel_ch' not in st.session_state: st.session_state.sel_ch = []

# --- SEARCH SECTION ---
with st.container():
    col_in, col_sr = st.columns([3, 1])
    m_id = col_in.text_input("ID Manga", placeholder="Masukkan ID Manga di sini...", label_visibility="collapsed")
    
    if col_sr.button("🔍 CARI", use_container_width=True):
        try:
            with st.spinner("Mencari data..."):
                m_res = requests.get(f"https://api.shngm.io/v1/manga/detail/{m_id}", headers=HEADERS).json()
                c_res = requests.get(f"https://api.shngm.io/v1/chapter/{m_id}/list?page=1&page_size=1500", headers=HEADERS).json()
                st.session_state.manga_data = {
                    "title": m_res["data"]["title"],
                    "raw_chapters": c_res["data"], 
                    "map": {f"Ch {c['chapter_number']}": c["chapter_id"] for c in c_res["data"]}
                }
                st.session_state.sel_ch = []
        except:
            st.error("Gagal mengambil data. Pastikan ID benar.")

# --- RESULT SECTION ---
if st.session_state.manga_data:
    m = st.session_state.manga_data
    
    st.markdown(f"""
    <div class='manga-card'>
        <p style='margin:0; color: #6B7280; font-size: 13px;'>Manga Ditemukan:</p>
        <h2 style='margin:0; color: #1F2937; font-size: 22px;'>{m['title']}</h2>
    </div>
    """, unsafe_allow_html=True)

    # --- OPTIONS ---
    col_opt1, col_opt2 = st.columns([2, 1])
    with col_opt1:
        order = st.radio("Urutan Daftar:", ["Ascending", "Descending"], horizontal=True)
    
    is_desc = (order == "Descending")
    sorted_chapters = sorted(m['raw_chapters'], key=lambda x: float(x['chapter_number']), reverse=is_desc)
    current_labels = [f"Ch {c['chapter_number']}" for c in sorted_chapters]

    # --- SELECT BUTTONS ---
    st.markdown('<div class="sub-btn">', unsafe_allow_html=True)
    c1, c2, _ = st.columns([1, 1, 1])
    if c1.button("Pilih Semua", use_container_width=True): st.session_state.sel_ch = current_labels
    if c2.button("Hapus Semua", use_container_width=True): st.session_state.sel_ch = []
    st.markdown('</div>', unsafe_allow_html=True)

    selected = st.multiselect("Pilih Chapter:", current_labels, key="sel_ch")

    # --- DOWNLOAD PROCESS ---
    if st.button("🚀 MULAI DOWNLOAD SEKARANG", use_container_width=True):
        if not selected:
            st.warning("Pilih minimal satu chapter!")
        else:
            main_zip = BytesIO()
            sorted_sel = sorted(selected, key=extract_number)
            
            pbar = st.progress(0)
            st_text = st.empty()

            try:
                with zipfile.ZipFile(main_zip, "w") as m_zip:
                    for i, label in enumerate(sorted_sel):
                        st_text.markdown(f"**⏳ Memproses:** `{label}`")
                        ch_id = m['map'][label]
                        
                        res = requests.get(f"https://api.shngm.io/v1/chapter/detail/{ch_id}", headers=HEADERS).json()["data"]
                        urls = [res["base_url"] + res["chapter"]["path"] + img for img in res["chapter"]["data"]]

                        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
                            imgs = list(ex.map(fetch_image, urls))

                        cbz_buf = BytesIO()
                        with zipfile.ZipFile(cbz_buf, "w") as c_zip:
                            for idx, img in enumerate(imgs):
                                if img: c_zip.writestr(f"{idx+1:03d}.jpg", img)
                        
                        m_zip.writestr(f"{sanitize_filename(label)}.cbz", cbz_buf.getvalue())
                        pbar.progress((i + 1) / len(sorted_sel))
                
                st_text.success(f"✅ Berhasil memproses {len(sorted_sel)} chapter!")
                
                # POPUP DOWNLOAD INSTAN
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

st.markdown("<br><hr><p style='text-align: center; color: #9CA3AF; font-size: 12px;'>Made with ❤️ for Manga Readers</p>", unsafe_allow_html=True)
