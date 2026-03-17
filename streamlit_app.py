import streamlit as st
import requests
from io import BytesIO
import zipfile
import re
import concurrent.futures

# --- CONFIG ---
st.set_page_config(page_title="SHNGM Downloader", page_icon="📖", layout="centered")

# --- MODERN & BRIGHT STYLING ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

    html, body, [class*="st-"] {
        font-family: 'Inter', sans-serif !important;
        font-size: 15px;
    }

    /* Background bersih */
    .main {
        background-color: #ffffff;
    }
    
    /* Input Search Bar yang bersih */
    .stTextInput input {
        border-radius: 12px !important;
        border: 2px solid #E5E7EB !important;
        padding: 12px !important;
        font-size: 16px !important;
        transition: border 0.3s;
    }
    .stTextInput input:focus {
        border-color: #3B82F6 !important;
    }

    /* Styling Tombol Umum */
    .stButton > button {
        border-radius: 12px !important;
        font-weight: 600 !important;
        height: 48px !important;
        transition: all 0.2s ease !important;
        border: none !important;
    }

    /* Tombol CARI (Biru Cerah) */
    div[data-testid="column"] .stButton > button {
        background-color: #3B82F6 !important;
        color: white !important;
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.2) !important;
    }
    div[data-testid="column"] .stButton > button:hover {
        background-color: #2563EB !important;
        transform: translateY(-1px);
    }

    /* Tombol Pilih & Hapus (Soft Blue) */
    .sub-btn .stButton > button {
        height: 38px !important;
        font-size: 13px !important;
        background-color: #EFF6FF !important;
        color: #1E40AF !important;
        border: 1px solid #DBEAFE !important;
    }
    .sub-btn .stButton > button:hover {
        background-color: #DBEAFE !important;
    }

    /* Tombol Download (Hijau Cerah & Segar) */
    .stDownloadButton > button {
        background: linear-gradient(135deg, #4ADE80 0%, #22C55E 100%) !important;
        color: white !important;
        box-shadow: 0 6px 20px rgba(34, 197, 94, 0.3) !important;
        width: 100% !important;
        height: 55px !important;
        font-size: 17px !important;
        border: none !important;
    }
    .stDownloadButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(34, 197, 94, 0.4) !important;
    }

    /* Card Hasil Pencarian */
    .manga-card {
        background-color: #F9FAFB;
        padding: 20px;
        border-radius: 16px;
        border: 1px solid #F3F4F6;
        margin-bottom: 20px;
        text-align: center;
    }

    /* Multiselect Styling */
    span[data-baseweb="tag"] {
        background-color: #3B82F6 !important;
        color: white !important;
        border-radius: 6px !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- LOGIC FUNCTIONS ---
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

# --- UI CONTENT ---
st.markdown("<h1 style='text-align: center; color: #111827; margin-bottom: 5px;'>📖 SHNGM <span style='color: #3B82F6;'>Downloader</span></h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #6B7280; font-size: 15px; margin-bottom: 30px;'>Unduh koleksi manga dengan cepat & mudah</p>", unsafe_allow_html=True)

if 'manga_data' not in st.session_state: st.session_state.manga_data = None
if 'sel_ch' not in st.session_state: st.session_state.sel_ch = []

# --- SEARCH BAR ---
col_in, col_sr = st.columns([3, 1])
m_id = col_in.text_input("ID Manga", placeholder="Tempel ID Manga di sini...", label_visibility="collapsed")

if col_sr.button("🔍 CARI", use_container_width=True):
    try:
        with st.spinner("Mengambil data..."):
            m_res = requests.get(f"https://api.shngm.io/v1/manga/detail/{m_id}", headers=HEADERS).json()
            c_res = requests.get(f"https://api.shngm.io/v1/chapter/{m_id}/list?page=1&page_size=1500", headers=HEADERS).json()
            st.session_state.manga_data = {
                "title": m_res["data"]["title"],
                "raw_chapters": c_res["data"], 
                "map": {f"Ch {c['chapter_number']}": c["chapter_id"] for c in c_res["data"]}
            }
            st.session_state.sel_ch = []
    except:
        st.error("Gagal! Pastikan ID Manga benar.")

# --- RESULT AREA ---
if st.session_state.manga_data:
    m = st.session_state.manga_data
    
    st.markdown(f"""
    <div class='manga-card'>
        <p style='margin:0; color: #6B7280; font-size: 13px; text-transform: uppercase; letter-spacing: 1px;'>Manga Ditemukan</p>
        <h2 style='margin:5px 0 0 0; color: #111827; font-size: 24px;'>{m['title']}</h2>
    </div>
    """, unsafe_allow_html=True)

    # Sorting & Selection
    order = st.radio("Urutan Daftar:", ["Ascending", "Descending"], horizontal=True)
    is_desc = (order == "Descending")
    
    sorted_chapters = sorted(m['raw_chapters'], key=lambda x: float(x['chapter_number']), reverse=is_desc)
    current_labels = [f"Ch {c['chapter_number']}" for c in sorted_chapters]

    # Tombol Pilih Semua / Hapus (Cerah)
    st.markdown('<div class="sub-btn">', unsafe_allow_html=True)
    c1, c2, _ = st.columns([1, 1, 1])
    if c1.button("Pilih Semua", use_container_width=True): st.session_state.sel_ch = current_labels
    if c2.button("Hapus Semua", use_container_width=True): st.session_state.sel_ch = []
    st.markdown('</div>', unsafe_allow_html=True)

    selected = st.multiselect("Pilih chapter untuk diunduh:", current_labels, key="sel_ch")

    # --- PROSES DOWNLOAD ---
    if st.button("🚀 MULAI DOWNLOAD", type="primary", use_container_width=True):
        if not selected:
            st.warning("Pilih chapter terlebih dahulu!")
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

                        with concurrent.futures.ThreadPoolExecutor(max_workers=15) as ex:
                            imgs = list(ex.map(fetch_image, urls))

                        cbz_buf = BytesIO()
                        with zipfile.ZipFile(cbz_buf, "w") as c_zip:
                            for idx, img in enumerate(imgs):
                                if img: c_zip.writestr(f"{idx+1:03d}.jpg", img)
                        
                        m_zip.writestr(f"{sanitize_filename(label)}.cbz", cbz_buf.getvalue())
                        pbar.progress((i + 1) / len(sorted_sel))
                
                st_text.success(f"✅ Siap! {len(sorted_sel)} Chapter berhasil diproses.")
                
                # POPUP INSTAN
                zip_ready = main_zip.getvalue()
                st.download_button(
                    label="📥 SIMPAN SEBAGAI .ZIP",
                    data=zip_ready,
                    file_name=f"{sanitize_filename(m['title'])}.zip",
                    mime="application/zip",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"Terjadi kesalahan: {e}")

st.markdown("<br><br><p style='text-align: center; color: #9CA3AF; font-size: 12px;'>Simple • Modern • Fast</p>", unsafe_allow_html=True)
