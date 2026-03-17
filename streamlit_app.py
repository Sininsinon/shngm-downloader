import streamlit as st
import requests
from io import BytesIO
import zipfile
import re
import concurrent.futures

# --- CONFIG ---
st.set_page_config(page_title="SHNGM Downloader", page_icon="📖", layout="centered")

# --- CUSTOM CSS (WARNA REQUEST: #181C14, #3C3D37, #697565, #ECDFCC) ---
st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

    .stApp {{
        background-color: #181C14 !important;
        color: #ECDFCC !important;
        font-family: 'Inter', sans-serif !important;
    }}

    .stTextInput input {{
        background-color: #3C3D37 !important;
        color: #ECDFCC !important;
        border: 1px solid #697565 !important;
        border-radius: 12px !important;
        height: 48px !important;
    }}
    
    .stButton > button {{
        background-color: #697565 !important;
        color: #ECDFCC !important;
        border-radius: 12px !important;
        border: none !important;
        font-weight: 600 !important;
        height: 48px !important;
        transition: all 0.2s ease !important;
    }}

    .stButton > button:hover {{
        background-color: #ECDFCC !important;
        color: #181C14 !important;
    }}

    .manga-card {{
        background-color: #3C3D37;
        padding: 20px;
        border-radius: 16px;
        border: 1px solid #697565;
        margin-bottom: 20px;
        text-align: center;
    }}

    .sub-btn .stButton > button {{
        height: 38px !important;
        font-size: 13px !important;
        background-color: #3C3D37 !important;
        border: 1px solid #697565 !important;
    }}

    /* Download Button Styling */
    .stDownloadButton > button {{
        background-color: #ECDFCC !important;
        color: #181C14 !important;
        height: 50px !important;
        font-size: 15px !important;
        margin-bottom: 10px !important;
    }}

    div[data-testid="stProgress"] > div > div > div > div {{
        background-color: #ECDFCC !important;
    }}

    h1, h2, h3, p, label {{ color: #ECDFCC !important; }}
    </style>
    """, unsafe_allow_html=True)

# --- FUNCTIONS ---
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
st.markdown("<h1 style='text-align: center;'>📖 SHNGM <span style='color: #697565;'>Downloader</span></h1>", unsafe_allow_html=True)

if 'manga_data' not in st.session_state: st.session_state.manga_data = None
if 'sel_ch' not in st.session_state: st.session_state.sel_ch = []
if 'download_results' not in st.session_state: st.session_state.download_results = []

# SEARCH BAR
col_in, col_sr = st.columns([3, 1.2])
m_id = col_in.text_input("ID Manga", placeholder="Masukkan ID...", label_visibility="collapsed")

if col_sr.button("🔍 CARI", use_container_width=True):
    try:
        with st.spinner("Wait..."):
            m_res = requests.get(f"https://api.shngm.io/v1/manga/detail/{m_id}", headers=HEADERS).json()
            c_res = requests.get(f"https://api.shngm.io/v1/chapter/{m_id}/list?page=1&page_size=1500", headers=HEADERS).json()
            st.session_state.manga_data = {
                "title": m_res["data"]["title"],
                "raw_chapters": c_res["data"], 
                "map": {f"Ch {c['chapter_number']}": c["chapter_id"] for c in c_res["data"]}
            }
            st.session_state.sel_ch = []
            st.session_state.download_results = [] # Clear previous results
    except: st.error("ID Tidak ditemukan!")

if st.session_state.manga_data:
    m = st.session_state.manga_data
    st.markdown(f"<div class='manga-card'><h2>{m['title']}</h2></div>", unsafe_allow_html=True)

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

    # DOWNLOAD LOGIC
    if st.button("🚀 MULAI PROSES", use_container_width=True):
        if not selected:
            st.warning("Pilih chapter dulu!")
        else:
            st.session_state.download_results = [] # Reset hasil download
            sorted_sel = sorted(selected, key=extract_number)
            
            # Membagi menjadi chunk berisi 5 chapter
            chunk_size = 5
            chunks = [sorted_sel[i:i + chunk_size] for i in range(0, len(sorted_sel), chunk_size)]
            
            total_chapters = len(sorted_sel)
            chapters_done = 0
            pbar = st.progress(0)
            st_text = st.empty()

            try:
                for idx, chunk in enumerate(chunks):
                    chunk_zip = BytesIO()
                    with zipfile.ZipFile(chunk_zip, "w") as m_zip:
                        for label in chunk:
                            st_text.markdown(f"⏳ **Grup {idx+1}/{len(chunks)} - Processing:** `{label}`")
                            ch_id = m['map'][label]
                            
                            res = requests.get(f"https://api.shngm.io/v1/chapter/detail/{ch_id}", headers=HEADERS).json()["data"]
                            urls = [res["base_url"] + res["chapter"]["path"] + img for img in res["chapter"]["data"]]

                            with concurrent.futures.ThreadPoolExecutor(max_workers=15) as ex:
                                imgs = list(ex.map(fetch_image, urls))

                            cbz_buf = BytesIO()
                            with zipfile.ZipFile(cbz_buf, "w") as c_zip:
                                for i_idx, img in enumerate(imgs):
                                    if img: c_zip.writestr(f"{i_idx+1:03d}.jpg", img)
                            
                            m_zip.writestr(f"{sanitize_filename(label)}.cbz", cbz_buf.getvalue())
                            
                            # Progress Update
                            chapters_done += 1
                            pbar.progress(chapters_done / total_chapters)
                    
                    # Simpan per ZIP grup ke session state
                    st.session_state.download_results.append({
                        "name": f"{sanitize_filename(m['title'])}_Part_{idx+1}.zip",
                        "data": chunk_zip.getvalue(),
                        "label": f"📥 DOWNLOAD GRUP {idx+1} ({chunk[0]} - {chunk[-1]})"
                    })
                
                st_text.success(f"✅ Selesai! {len(chunks)} File ZIP siap didownload.")
            except Exception as e:
                st.error(f"Error: {e}")

    # Tampilkan tombol download jika ada hasil
    if st.session_state.download_results:
        st.markdown("<hr>", unsafe_allow_html=True)
        st.subheader("Daftar File Download:")
        for res in st.session_state.download_results:
            st.download_button(
                label=res["label"],
                data=res["data"],
                file_name=res["name"],
                mime="application/zip",
                use_container_width=True
            )

st.markdown("<br><p style='text-align: center; color: #697565; font-size: 12px;'>SHNGM Downloader Tool • Batch 5 Chapter</p>", unsafe_allow_html=True)
