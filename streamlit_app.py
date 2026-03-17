import streamlit as st
import requests
from io import BytesIO
import zipfile
import re
import concurrent.futures
import time
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="SHNGM Downloader Pro (CBZ Edition)", page_icon="⚡", layout="wide")

# Setup Session dengan Retry Strategy
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

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Referer": "https://shngm.io/",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}

# --- FUNGSI UTILITY ---
def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name).strip().replace(" ", "_")

def extract_number(text):
    nums = re.findall(r"[-+]?\d*\.\d+|\d+", text)
    if nums:
        val = float(nums[0])
        return int(val) if val.is_integer() else val
    return 0

def fetch_image(url):
    """Download gambar sebagai bytes mentah (sangat cepat)"""
    try:
        r = session.get(url, headers=headers, timeout=20)
        return r.content if r.status_code == 200 else None
    except:
        return None

# --- LOGIKA SESSION STATE ---
if 'manga_data' not in st.session_state:
    st.session_state.manga_data = None

def select_all():
    if st.session_state.manga_data:
        st.session_state.sel_ch = st.session_state.manga_data['labels']

def deselect_all():
    st.session_state.sel_ch = []

# --- UI HEADER ---
st.title("⚡ SHNGM CBZ Downloader")
st.caption("Mendownload chapter dalam format .cbz (Jauh lebih cepat tanpa konversi PDF)")

col_input, col_search = st.columns([4, 1])
with col_input:
    manga_id_input = st.text_input("Manga ID", placeholder="Masukkan ID Manga...", label_visibility="collapsed")
with col_search:
    search_btn = st.button("🔍 CARI MANGA", use_container_width=True, type="primary")

if search_btn and manga_id_input:
    try:
        with st.spinner("Sedang mencari manga..."):
            m_res = session.get(f"https://api.shngm.io/v1/manga/detail/{manga_id_input}", headers=headers).json()
            title = m_res["data"]["title"]
            
            c_res = session.get(f"https://api.shngm.io/v1/chapter/{manga_id_input}/list?page=1&page_size=1500&sort_by=chapter_number&sort_order=asc", headers=headers).json()
            chapters = c_res["data"]
            
            chapter_map = {f"Chapter {c['chapter_number']}": c["chapter_id"] for c in chapters}
            chapter_labels = sorted(list(chapter_map.keys()), key=extract_number)

            st.session_state.manga_data = {
                "title": title,
                "map": chapter_map,
                "labels": chapter_labels
            }
            st.session_state.sel_ch = [] 
    except Exception as e:
        st.error(f"Gagal memuat data. Pastikan ID benar.")

if st.session_state.manga_data:
    m_info = st.session_state.manga_data
    st.divider()
    st.subheader(f"📖 {m_info['title']}")

    col_all, col_none = st.columns([1, 1])
    with col_all: st.button("✅ Pilih Semua", on_click=select_all, use_container_width=True)
    with col_none: st.button("❌ Hapus Semua", on_click=deselect_all, use_container_width=True)

    selected = st.multiselect("Daftar Chapter:", m_info['labels'], key="sel_ch")

    if st.button("🚀 MULAI DOWNLOAD (.CBZ)", type="primary", use_container_width=True):
        if not selected:
            st.error("Pilih minimal satu chapter!")
        else:
            # Buffer utama untuk file ZIP yang berisi kumpulan .cbz
            main_zip_buffer = BytesIO()
            sorted_selected = sorted(selected, key=extract_number)
            
            ch_nums = [extract_number(s) for s in sorted_selected]
            range_str = f"Ch_{ch_nums[0]}" if len(ch_nums) == 1 else f"Ch_{ch_nums[0]}-{ch_nums[-1]}"
            final_filename = f"{sanitize_filename(m_info['title'])}_{range_str}.zip"

            progress_bar = st.progress(0)
            status_text = st.empty()

            try:
                with zipfile.ZipFile(main_zip_buffer, "w", zipfile.ZIP_DEFLATED) as main_zip:
                    for i, ch_label in enumerate(sorted_selected):
                        status_text.text(f"⏳ Mendownload {ch_label} (Tanpa PDF, langsung CBZ)...")
                        
                        ch_id = m_info['map'][ch_label]
                        ch_detail_res = session.get(f"https://api.shngm.io/v1/chapter/detail/{ch_id}", headers=headers, timeout=30)
                        ch_detail = ch_detail_res.json()["data"]
                        
                        urls = [ch_detail["base_url"] + ch_detail["chapter"]["path"] + img for img in ch_detail["chapter"]["data"]]

                        # Download gambar secara paralel
                        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                            img_results = list(executor.map(fetch_image, urls))

                        # BUAT FILE CBZ (Sebenarnya ZIP berisi gambar mentah)
                        cbz_buffer = BytesIO()
                        with zipfile.ZipFile(cbz_buffer, "w", zipfile.ZIP_STORED) as cbz:
                            for idx, img_bytes in enumerate(img_results):
                                if img_bytes:
                                    # Penamaan file di dalam CBZ: 001.jpg, 002.jpg, dst
                                    cbz.writestr(f"{idx+1:03d}.jpg", img_bytes)
                        
                        # Masukkan file .cbz ke dalam ZIP utama
                        main_zip.writestr(f"{sanitize_filename(ch_label)}.cbz", cbz_buffer.getvalue())
                        
                        progress_bar.progress((i + 1) / len(sorted_selected))
                        time.sleep(0.1) # Jeda minimal untuk stabilitas

                status_text.success(f"✅ Berhasil memproses {len(selected)} chapter!")
                
                def get_data():
                    return zip_buffer.getvalue()
                
                st.download_button(
                    label="📥 DOWNLOAD SEKARANG",
                    data=get_data,  # Memberikan fungsi, bukan data mentah
                    file_name=final_zip_name,
                    mime="application/zip",
                    use_container_width=True
                )
                 except Exception as e:
                st.error(f"Terjadi kesalahan: {e}")
