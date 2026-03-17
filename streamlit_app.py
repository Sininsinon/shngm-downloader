import streamlit as st
import requests
from io import BytesIO
import zipfile
import re
import concurrent.futures
import time

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
        m_res = requests.get(f"https://api.shngm.io/v1/manga/detail/{m_id}", headers=HEADERS).json()
        c_res = requests.get(f"https://api.shngm.io/v1/chapter/{m_id}/list?page=1&page_size=1500", headers=HEADERS).json()
        chapters = sorted(c_res["data"], key=lambda x: float(x['chapter_number']))
        st.session_state.manga_data = {
            "title": m_res["data"]["title"],
            "map": {f"Chapter {c['chapter_number']}": c["chapter_id"] for c in chapters},
            "labels": [f"Chapter {c['chapter_number']}" for c in chapters]
        }
    except: st.error("ID Salah!")

# Daftar Chapter & Proses
if st.session_state.manga_data:
    m = st.session_state.manga_data
    st.subheader(f"Manga: {m['title']}")

    # Tombol Pilih
    c1, c2 = st.columns(2)
    if c1.button("Pilih Semua"): st.session_state.sel_ch = m['labels']
    if c2.button("Hapus Semua"): st.session_state.sel_ch = []

    selected = st.multiselect("Pilih Chapter:", m['labels'], key="sel_ch")

    # Tombol Mulai (Tampilan Normal ke bawah)
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
                        st_text.text(f"⏳ Mendownload {label}...")
                        ch_id = m['map'][label]
                        res = requests.get(f"https://api.shngm.io/v1/chapter/detail/{ch_id}", headers=HEADERS).json()["data"]
                        urls = [res["base_url"] + res["chapter"]["path"] + img for img in res["chapter"]["data"]]

                        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
                            imgs = list(ex.map(fetch_image, urls))

                        # Build CBZ
                        cbz_buf = BytesIO()
                        with zipfile.ZipFile(cbz_buf, "w") as c_zip:
                            for idx, img in enumerate(imgs):
                                if img: c_zip.writestr(f"{idx+1:03d}.jpg", img)
                        
                        m_zip.writestr(f"{sanitize_filename(label)}.cbz", cbz_buf.getvalue())
                        pbar.progress((i + 1) / len(sorted_sel))
                
                st_text.success("✅ Berhasil!")
                
                # Fungsi agar popup cepat (Deferred Download)
                def get_data(): return main_zip.getvalue()

                st.download_button(
                    label="📥 SIMPAN FILE ZIP",
                    data=get_data,
                    file_name=f"{sanitize_filename(m['title'])}.zip",
                    mime="application/zip",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"Error: {e}")
