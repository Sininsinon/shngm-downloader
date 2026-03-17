import streamlit as st
import requests
from io import BytesIO
import zipfile
import re
import concurrent.futures

# --- CONFIG ---
st.set_page_config(page_title="SHNGM Downloader", page_icon="📖")

# --- CUSTOM CSS (FONT & TOMBOL LEBIH BESAR & NYAMAN) ---
st.markdown("""
    <style>
    /* Ukuran Font Global sedikit lebih besar agar terbaca jelas */
    html, body, [class*="st-"] {
        font-size: 15px !important; 
    }
    h1 { font-size: 1.8rem !important; }
    
    /* Memperbesar Search Bar & Input */
    .stTextInput input {
        font-size: 16px !important;
        padding: 10px !important;
        height: 45px !important;
    }

    /* Memperbesar Tombol Cari & Tombol Utama */
    .stButton > button {
        font-size: 14px !important;
        padding: 8px 16px !important;
        height: 45px !important;
        border-radius: 8px !important;
    }

    /* Tombol Pilih/Hapus Semua (Sedikit lebih kecil dari tombol utama tapi tetap nyaman) */
    .small-btn-container .stButton > button {
        font-size: 13px !important;
        height: 38px !important;
        padding: 4px 10px !important;
    }

    /* Jarak antar elemen agar tidak menempel */
    .stMultiSelect {
        margin-top: 10px !important;
    }
    
    /* Tombol Download Hijau Mencolok */
    div.stDownloadButton > button {
        background-color: #28a745 !important;
        color: white !important;
        font-weight: bold !important;
        height: 50px !important;
        font-size: 16px !important;
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

# Input & Search (Dibuat lebih besar)
col_in, col_sr = st.columns([3, 1.2])
m_id = col_in.text_input("ID Manga", placeholder="Masukkan ID...", label_visibility="collapsed")

if col_sr.button("🔍 CARI", use_container_width=True):
    try:
        with st.spinner("Loading..."):
            m_res = requests.get(f"https://api.shngm.io/v1/manga/detail/{m_id}", headers=HEADERS).json()
            c_res = requests.get(f"https://api.shngm.io/v1/chapter/{m_id}/list?page=1&page_size=1500", headers=HEADERS).json()
            st.session_state.manga_data = {
                "title": m_res["data"]["title"],
                "raw_chapters": c_res["data"], 
                "map": {f"Ch {c['chapter_number']}": c["chapter_id"] for c in c_res["data"]}
            }
            st.session_state.sel_ch = []
    except: st.error("ID Manga tidak ditemukan!")

if st.session_state.manga_data:
    m = st.session_state.manga_data
    st.markdown(f"### {m['title']}")

    # --- FITUR SORTING ---
    order = st.radio("Urutan List:", ["Ascending", "Descending"], horizontal=True)
    is_desc = (order == "Descending")

    # Re-sort data berdasarkan pilihan
    sorted_chapters = sorted(m['raw_chapters'], key=lambda x: float(x['chapter_number']), reverse=is_desc)
    current_labels = [f"Ch {c['chapter_number']}" for c in sorted_chapters]

    # Tombol Pilih/Hapus (Dalam container CSS khusus agar ukuran terkontrol)
    st.markdown('<div class="small-btn-container">', unsafe_allow_html=True)
    c1, c2, _ = st.columns([1, 1, 1])
    if c1.button("Pilih Semua", use_container_width=True): 
        st.session_state.sel_ch = current_labels
    if c2.button("Hapus Semua", use_container_width=True): 
        st.session_state.sel_ch = []
    st.markdown('</div>', unsafe_allow_html=True)

    # Multiselect (Font otomatis ikut besar dari CSS global)
    selected = st.multiselect("Pilih Chapter yang ingin didownload:", current_labels, key="sel_ch")

    # Tombol Mulai (Besar & Hijau)
    if st.button("🚀 MULAI PROSES DOWNLOAD (.CBZ)", type="primary", use_container_width=True):
        if not selected:
            st.warning("Silahkan pilih chapter terlebih dahulu!")
        else:
            main_zip = BytesIO()
            # Sortir ke angka agar urutan file di dalam ZIP rapi
            sorted_sel = sorted(selected, key=extract_number)
            
            pbar = st.progress(0)
            st_text = st.empty()

            try:
                with zipfile.ZipFile(main_zip, "w") as m_zip:
                    for i, label in enumerate(sorted_sel):
                        st_text.text(f"⏳ Sedang memproses {label}...")
                        ch_id = m['map'][label]
                        
                        # Fetch detail chapter
                        res_data = requests.get(f"https://api.shngm.io/v1/chapter/detail/{ch_id}", headers=HEADERS).json()["data"]
                        base = res_data["base_url"]
                        path = res_data["chapter"]["path"]
                        urls = [base + path + img for img in res_data["chapter"]["data"]]

                        # Download gambar
                        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
                            imgs = list(ex.map(fetch_image, urls))

                        # Buat file CBZ di memori
                        cbz_buf = BytesIO()
                        with zipfile.ZipFile(cbz_buf, "w") as c_zip:
                            for idx, img in enumerate(imgs):
                                if img: c_zip.writestr(f"{idx+1:03d}.jpg", img)
                        
                        # Masukkan CBZ ke ZIP utama
                        m_zip.writestr(f"{sanitize_filename(label)}.cbz", cbz_buf.getvalue())
                        pbar.progress((i + 1) / len(sorted_sel))
                
                st_text.success("✅ Selesai! Klik tombol di bawah untuk menyimpan file.")
                
                # POPUP DOWNLOAD INSTAN (Menggunakan data yang sudah ditarik ke memori)
                zip_ready = main_zip.getvalue()
                st.download_button(
                    label="📥 SIMPAN FILE ZIP",
                    data=zip_ready,
                    file_name=f"{sanitize_filename(m['title'])}.zip",
                    mime="application/zip",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"Terjadi kesalahan teknis: {e}")
