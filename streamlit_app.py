import streamlit as st
import requests
from io import BytesIO
import zipfile
import re
import concurrent.futures
import time
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(page_title="SHNGM CBZ Downloader", page_icon="⚡", layout="wide")

# CSS untuk Fixed Footer (Tombol Download tetap di bawah)
st.markdown("""
    <style>
    .main-content { margin-bottom: 150px; }
    div[data-testid="stVerticalBlock"] > div:has(div.fixed-footer) {
        position: fixed;
        bottom: 0; left: 0; width: 100%;
        background-color: white;
        z-index: 999;
        padding: 15px 5%;
        border-top: 1px solid #ddd;
        box-shadow: 0 -5px 10px rgba(0,0,0,0.1);
    }
    </style>
    """, unsafe_allow_html=True)

# Setup Session agar koneksi stabil
def create_session():
    session = requests.Session()
    retry_strategy = Retry(
        total=5,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

session = create_session()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://shngm.io/"
}

# --- 2. UTILS ---
def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name).strip().replace(" ", "_")

def extract_number(text):
    nums = re.findall(r"(\d+\.?\d*)", str(text))
    return float(nums[0]) if nums else 0

def fetch_image(url):
    try:
        r = session.get(url, headers=HEADERS, timeout=20)
        return r.content if r.status_code == 200 else None
    except:
        return None

# --- 3. SESSION STATE ---
if 'manga_data' not in st.session_state:
    st.session_state.manga_data = None
if 'sel_ch' not in st.session_state:
    st.session_state.sel_ch = []

def select_all():
    if st.session_state.manga_data:
        st.session_state.sel_ch = st.session_state.manga_data['labels']

def deselect_all():
    st.session_state.sel_ch = []

# --- 4. UI HEADER ---
st.title("⚡ SHNGM CBZ Downloader")

col_in, col_sr = st.columns([4, 1])
m_id = col_in.text_input("Manga ID", placeholder="Masukkan ID Manga...", label_visibility="collapsed")

if col_sr.button("🔍 CARI MANGA", use_container_width=True, type="primary"):
    if m_id:
        try:
            with st.spinner("Mencari manga..."):
                m_res = session.get(f"https://api.shngm.io/v1/manga/detail/{m_id}", headers=HEADERS).json()
                title = m_res["data"]["title"]
                c_res = session.get(f"https://api.shngm.io/v1/chapter/{m_id}/list?page=1&page_size=1500", headers=HEADERS).json()
                chapters = sorted(c_res["data"], key=lambda x: float(x['chapter_number']))
                
                st.session_state.manga_data = {
                    "title": title,
                    "map": {f"Chapter {c['chapter_number']}": c["chapter_id"] for c in chapters},
                    "labels": [f"Chapter {c['chapter_number']}" for c in chapters]
                }
                st.session_state.sel_ch = []
        except:
            st.error("Gagal! Pastikan ID benar.")

# --- 5. DAFTAR CHAPTER ---
if st.session_state.manga_data:
    m_info = st.session_state.manga_data
    st.markdown('<div class="main-content">', unsafe_allow_html=True)
    st.subheader(f"📖 {m_info['title']}")

    c1, c2 = st.columns(2)
    with c1: st.button("✅ Pilih Semua", on_click=select_all, use_container_width=True)
    with c2: st.button("❌ Hapus Semua", on_click=deselect_all, use_container_width=True)

    selected = st.multiselect("Pilih Chapter:", m_info['labels'], key="sel_ch")
    st.markdown('</div>', unsafe_allow_html=True)

    # --- 6. FIXED FOOTER (PROSES & DOWNLOAD) ---
    with st.container():
        st.markdown('<div class="fixed-footer">', unsafe_allow_html=True)
        col_btn, col_status = st.columns([1, 2])
        
        btn_start = col_btn.button("🚀 MULAI DOWNLOAD (.CBZ)", type="primary", use_container_width=True)
        
        status_area = col_status.empty()
        prog_bar = col_status.empty()
        dl_area = col_status.empty()

        if btn_start:
            if not selected:
                status_area.error("Pilih chapter dulu!")
            else:
                main_zip_buffer = BytesIO()
                sorted_sel = sorted(selected, key=extract_number)
                
                # Penamaan file
                nums = [extract_number(s) for s in sorted_sel]
                range_nm = f"Ch_{nums[0]}" if len(nums) == 1 else f"Ch_{nums[0]}-{nums[-1]}"
                final_nm = f"{sanitize_filename(m_info['title'])}_{range_nm}.zip"

                try:
                    with zipfile.ZipFile(main_zip_buffer, "w", zipfile.ZIP_DEFLATED) as main_zip:
                        for i, label in enumerate(sorted_sel):
                            status_area.text(f"⏳ Mendownload {label}...")
                            prog_bar.progress((i + 1) / len(sorted_sel))
                            
                            ch_id = m_info['map'][label]
                            res = session.get(f"https://api.shngm.io/v1/chapter/detail/{ch_id}", headers=HEADERS, timeout=30).json()["data"]
                            urls = [res["base_url"] + res["chapter"]["path"] + img for img in res["chapter"]["data"]]

                            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
                                img_results = list(ex.map(fetch_image, urls))

                            # Buat CBZ (ZIP mentah)
                            cbz_buffer = BytesIO()
                            with zipfile.ZipFile(cbz_buffer, "w", zipfile.ZIP_STORED) as cbz:
                                for idx, img_bytes in enumerate(img_results):
                                    if img_bytes:
                                        cbz.writestr(f"{idx+1:03d}.jpg", img_bytes)
                            
                            main_zip.writestr(f"{sanitize_filename(label)}.cbz", cbz_buffer.getvalue())
                            time.sleep(0.1)

                    status_area.success(f"✅ Selesai! {len(selected)} Chapter siap.")
                    
                    # Tombol Download Final
                    dl_area.download_button(
                        label=f"📥 KLIK UNTUK SIMPAN ZIP",
                        data=main_zip_buffer.getvalue(),
                        file_name=final_nm,
                        mime="application/zip",
                        use_container_width=True
                    )
                except Exception as e:
                    status_area.error(f"Terjadi kesalahan: {e}")
        
        st.markdown('</div>', unsafe_allow_html=True)
