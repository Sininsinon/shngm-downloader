import streamlit as st
import requests
from io import BytesIO
import zipfile
import re
import concurrent.futures

# --- CONFIG ---
st.set_page_config(page_title="SHNGM Downloader", page_icon="📖")

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
st.title("📖 SHNGM Manga Downloader")

if 'manga_data' not in st.session_state: st.session_state.manga_data = None
if 'sel_ch' not in st.session_state: st.session_state.sel_ch = []

# Input & Search
col_in, col_sr = st.columns([4, 1])
m_id = col_in.text_input("Manga ID", placeholder="Masukkan ID Manga...", label_visibility="collapsed")

if col_sr.button("🔍 CARI", use_container_width=True):
    try:
        with st.spinner("Mengambil data..."):
            m_res = requests.get(f"https://api.shngm.io/v1/manga/detail/{m_id}", headers=HEADERS).json()
            c_res = requests.get(f"https://api.shngm.io/v1/chapter/{m_id}/list?page=1&page_size=1500", headers=HEADERS).json()
            
            # Simpan data mentah
            chapters = c_res["data"] 
            st.session_state.manga_data = {
                "title": m_res["data"]["title"],
                "raw_chapters": chapters, # Simpan list mentah untuk diurutkan nanti
                "map": {f"Chapter {c['chapter_number']}": c["chapter_id"] for c in chapters}
            }
            st.session_state.sel_ch = [] # Reset pilihan saat cari manga baru
    except Exception as e: 
        st.error(f"ID Salah atau Error: {e}")

# Daftar Chapter & Proses
if st.session_state.manga_data:
    m = st.session_state.manga_data
    st.subheader(f"Manga: {m['title']}")

    # --- FITUR SORTING ---
    order = st.radio("Urutan Chapter:", ["Terkecil (Ascending)", "Terbesar (Descending)"], horizontal=True)
    is_desc = True if "Terbesar" in order else False

    # Buat label list berdasarkan urutan yang dipilih
    sorted_chapters = sorted(m['raw_chapters'], key=lambda x: float(x['chapter_number']), reverse=is_desc)
    current_labels = [f"Chapter {c['chapter_number']}" for c in sorted_chapters]

    # Tombol Pilih
    c1, c2 = st.columns(2)
    if c1.button("Pilih Semua"): 
        st.session_state.sel_ch = current_labels
    if c2.button("Hapus Semua"): 
        st.session_state.sel_ch = []

    # Multiselect akan mengikuti urutan current_labels
    selected = st.multiselect("Pilih Chapter:", current_labels, key="sel_ch")

    # Tombol Mulai
    if st.button("🚀 MULAI DOWNLOAD (.CBZ)", type="primary", use_container_width=True):
        if not selected:
            st.warning("Pilih chapter dulu!")
        else:
            main_zip = BytesIO()
            # Selalu download dalam urutan terkecil ke terbesar agar file di dalam ZIP rapi
            sorted_sel = sorted(selected, key=extract_number)
            
            pbar = st.progress(0)
            st_text = st.empty()

            try:
                with zipfile.ZipFile(main_zip, "w") as m_zip:
                    for i, label in enumerate(sorted_sel):
                        st_text.text(f"⏳ Mendownload {label}...")
                        ch_id = m['map'][label]
                        
                        # Get Detail Chapter (Image URLs)
                        res_data = requests.get(f"https://api.shngm.io/v1/chapter/detail/{ch_id}", headers=HEADERS).json()["data"]
                        base = res_data["base_url"]
                        path = res_data["chapter"]["path"]
                        urls = [base + path + img for img in res_data["chapter"]["data"]]

                        # Download images parallel
                        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
                            imgs = list(ex.map(fetch_image, urls))

                        # Build individual CBZ
                        cbz_buf = BytesIO()
                        with zipfile.ZipFile(cbz_buf, "w") as c_zip:
                            for idx, img in enumerate(imgs):
                                if img: 
                                    c_zip.writestr(f"{idx+1:03d}.jpg", img)
                        
                        # Simpan CBZ ke dalam ZIP Utama
                        m_zip.writestr(f"{sanitize_filename(label)}.cbz", cbz_buf.getvalue())
                        pbar.progress((i + 1) / len(sorted_sel))
                
                st_text.success("✅ Semua chapter berhasil diproses!")
                
                st.download_button(
                    label="📥 SIMPAN FILE ZIP",
                    data=main_zip.getvalue(),
                    file_name=f"{sanitize_filename(m['title'])}.zip",
                    mime="application/zip",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"Terjadi kesalahan: {e}")
