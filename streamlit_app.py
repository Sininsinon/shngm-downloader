import streamlit as st
import requests
from io import BytesIO
import zipfile
import re
import concurrent.futures

# --- CONFIG ---
st.set_page_config(page_title="SHNGM Downloader", page_icon="📖")

# --- CUSTOM CSS UNTUK MOBILE ---
st.markdown("""
    <style>
    /* Mengecilkan font global */
    html, body, [class*="st-"] {
        font-size: 14px !important;
    }
    h1 { font-size: 1.6rem !important; }
    h2 { font-size: 1.3rem !important; }
    h3 { font-size: 1.1rem !important; }
    
    /* Mengecilkan padding dan font tombol */
    .stButton > button {
        font-size: 12px !important;
        padding: 4px 8px !important;
        height: auto !important;
        min-height: 30px !important;
    }
    
    /* Mengecilkan jarak antar elemen */
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 2rem !important;
    }

    /* Styling khusus radio button agar lebih rapat */
    div[data-testid="stRadio"] > label {
        font-size: 13px !important;
    }
    </style>
    """, unsafe_allow_html=True)

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

# --- UI ---
st.title("📖 SHNGM Downloader")

if 'manga_data' not in st.session_state: st.session_state.manga_data = None
if 'sel_ch' not in st.session_state: st.session_state.sel_ch = []

# Input & Search (Dibuat lebih compact)
col_in, col_sr = st.columns([3, 1])
m_id = col_in.text_input("ID Manga", placeholder="ID...", label_visibility="collapsed")

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
    except: st.error("ID Salah!")

# Daftar Chapter & Proses
if st.session_state.manga_data:
    m = st.session_state.manga_data
    st.markdown(f"**Manga:** {m['title']}")

    # --- FITUR SORTING ---
    order = st.radio("Urutan:", ["Ascending", "Descending"], horizontal=True)
    is_desc = True if order == "Descending" else False

    # Buat label list berdasarkan urutan
    sorted_chapters = sorted(m['raw_chapters'], key=lambda x: float(x['chapter_number']), reverse=is_desc)
    current_labels = [f"Ch {c['chapter_number']}" for c in sorted_chapters]

    # Tombol Pilih (Kecil)
    c1, c2, c3 = st.columns([1, 1, 1])
    if c1.button("Pilih Semua"): 
        st.session_state.sel_ch = current_labels
    if c2.button("Hapus Semua"): 
        st.session_state.sel_ch = []

    # Multiselect
    selected = st.multiselect("Pilih Chapter:", current_labels, key="sel_ch")

    # Tombol Mulai
    if st.button("🚀 MULAI DOWNLOAD (.CBZ)", type="primary", use_container_width=True):
        if not selected:
            st.warning("Pilih chapter dulu!")
        else:
            main_zip = BytesIO()
            sorted_sel = sorted(selected, key=extract_number)
            
            pbar = st.progress(0)
            st_text = st.empty()

            try:
                with zipfile.ZipFile(main_zip, "w") as m_zip:
                    for i, label in enumerate(sorted_sel):
                        st_text.text(f"⏳ {label}...")
                        ch_id = m['map'][label]
                        
                        res_data = requests.get(f"https://api.shngm.io/v1/chapter/detail/{ch_id}", headers=HEADERS).json()["data"]
                        base = res_data["base_url"]
                        path = res_data["chapter"]["path"]
                        urls = [base + path + img for img in res_data["chapter"]["data"]]

                        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
                            imgs = list(ex.map(fetch_image, urls))

                        cbz_buf = BytesIO()
                        with zipfile.ZipFile(cbz_buf, "w") as c_zip:
                            for idx, img in enumerate(imgs):
                                if img: c_zip.writestr(f"{idx+1:03d}.jpg", img)
                        
                        m_zip.writestr(f"{sanitize_filename(label)}.cbz", cbz_buf.getvalue())
                        pbar.progress((i + 1) / len(sorted_sel))
                
                st_text.success("✅ Selesai!")
                st.download_button(
                    label="📥 SIMPAN ZIP",
                    data=main_zip.getvalue(),
                    file_name=f"{sanitize_filename(m['title'])}.zip",
                    mime="application/zip",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"Error: {e}")
