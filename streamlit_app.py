import streamlit as st
import requests
from io import BytesIO
import zipfile
import re
import concurrent.futures

# --- CONFIG ---
st.set_page_config(page_title="SHNGM Downloader", page_icon="📖", layout="centered")

# --- CUSTOM CSS (PALET WARNA SESUAI REQUEST) ---
st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    .stApp {{ background-color: #181C14 !important; color: #ECDFCC !important; font-family: 'Inter', sans-serif !important; }}
    .stTextInput input, .stNumberInput input {{ background-color: #3C3D37 !important; color: #ECDFCC !important; border: 1px solid #697565 !important; border-radius: 12px !important; height: 48px !important; }}
    .stButton > button {{ background-color: #697565 !important; color: #ECDFCC !important; border-radius: 12px !important; border: none !important; font-weight: 600 !important; height: 48px !important; transition: all 0.2s ease !important; width: 100%; }}
    .stButton > button:hover {{ background-color: #ECDFCC !important; color: #181C14 !important; }}
    .manga-card {{ background-color: #3C3D37; padding: 20px; border-radius: 16px; border: 1px solid #697565; margin-bottom: 20px; text-align: center; }}
    .stDownloadButton > button {{ background-color: #ECDFCC !important; color: #181C14 !important; height: 55px !important; font-size: 16px !important; font-weight: bold !important; margin-bottom: 15px !important; border: 2px solid #697565 !important; box-shadow: 0 4px 10px rgba(0,0,0,0.3) !important; }}
    div[data-testid="stProgress"] > div > div > div > div {{ background-color: #ECDFCC !important; }}
    h1, h2, h3, p, label {{ color: #ECDFCC !important; }}
    span[data-baseweb="tag"] {{ background-color: #697565 !important; color: #ECDFCC !important; }}
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

# --- SESSION STATE INITIALIZATION ---
if 'manga_data' not in st.session_state: st.session_state.manga_data = None
if 'dl_list' not in st.session_state: st.session_state.dl_list = []
if 'processing' not in st.session_state: st.session_state.processing = False

# --- UI CONTENT ---
st.markdown("<h1 style='text-align: center;'>📖 SHNGM <span style='color: #697565;'>Downloader</span></h1>", unsafe_allow_html=True)

# SEARCH BAR
col_in, col_sr = st.columns([3, 1])
m_id = col_in.text_input("ID Manga", placeholder="Masukkan ID Manga...", label_visibility="collapsed")

if col_sr.button("🔍 CARI"):
    try:
        with st.spinner("Mencari Manga..."):
            m_res = requests.get(f"https://api.shngm.io/v1/manga/detail/{m_id}", headers=HEADERS).json()
            c_res = requests.get(f"https://api.shngm.io/v1/chapter/{m_id}/list?page=1&page_size=1500", headers=HEADERS).json()
            chapters_sorted = sorted(c_res["data"], key=lambda x: float(x['chapter_number']))
            st.session_state.manga_data = {
                "title": m_res["data"]["title"],
                "raw_chapters": chapters_sorted, 
                "map": {f"Ch {c['chapter_number']}": c["chapter_id"] for c in chapters_sorted}
            }
            st.session_state.dl_list = [] # Reset download list
            st.rerun()
    except: st.error("ID Manga tidak ditemukan!")

if st.session_state.manga_data:
    m = st.session_state.manga_data
    st.markdown(f"<div class='manga-card'><p style='color:#697565; margin:0;'>Manga:</p><h2 style='margin:0;'>{m['title']}</h2></div>", unsafe_allow_html=True)

    # --- PILIHAN MODE ---
    mode = st.radio("Metode Seleksi:", ["Pilih Manual", "Batch (Rentang)"], horizontal=True)
    
    selected_labels = []

    if mode == "Pilih Manual":
        order = st.radio("Urutan:", ["Ascending", "Descending"], horizontal=True)
        is_desc = (order == "Descending")
        current_labels = [f"Ch {c['chapter_number']}" for c in sorted(m['raw_chapters'], key=lambda x: float(x['chapter_number']), reverse=is_desc)]
        
        c1, c2 = st.columns(2)
        if c1.button("Pilih Semua"): st.session_state.manual_sel = current_labels
        if c2.button("Hapus Semua"): st.session_state.manual_sel = []
        
        selected_labels = st.multiselect("Daftar Chapter:", current_labels, key="manual_sel")

    else:
        all_nums = [float(c['chapter_number']) for c in m['raw_chapters']]
        col_b1, col_b2 = st.columns(2)
        start_ch = col_b1.number_input("Dari Ch:", min_value=min(all_nums), max_value=max(all_nums), value=min(all_nums))
        end_ch = col_b2.number_input("Sampai Ch:", min_value=min(all_nums), max_value=max(all_nums), value=max(all_nums))
        
        selected_labels = [f"Ch {c['chapter_number']}" for c in m['raw_chapters'] if start_ch <= float(c['chapter_number']) <= end_ch]
        st.info(f"💡 {len(selected_labels)} chapter terpilih.")

    # --- PROSES DOWNLOAD ---
    if st.button("🚀 MULAI PROSES SEKARANG", type="primary"):
        if not selected_labels:
            st.warning("Pilih chapter dulu!")
        else:
            st.session_state.dl_list = [] # Bersihkan list lama
            sorted_sel = sorted(selected_labels, key=extract_number)
            
            # Pecah jadi 5 chapter per ZIP
            batch_size = 5
            batches = [sorted_sel[i:i + batch_size] for i in range(0, len(sorted_sel), batch_size)]
            
            pbar = st.progress(0)
            status_text = st.empty()

            try:
                for b_idx, batch in enumerate(batches):
                    batch_zip_io = BytesIO()
                    with zipfile.ZipFile(batch_zip_io, "w") as m_zip:
                        for label in batch:
                            status_text.markdown(f"⏳ **Grup {b_idx+1}:** Memproses `{label}`...")
                            ch_id = m['map'][label]
                            
                            res = requests.get(f"https://api.shngm.io/v1/chapter/detail/{ch_id}", headers=HEADERS).json()["data"]
                            urls = [res["base_url"] + res["chapter"]["path"] + img for img in res["chapter"]["data"]]

                            # Threading ditingkatkan ke 20 agar lebih cepat
                            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
                                imgs = list(ex.map(fetch_image, urls))

                            cbz_buf = BytesIO()
                            with zipfile.ZipFile(cbz_buf, "w") as c_zip:
                                for i, img in enumerate(imgs):
                                    if img: c_zip.writestr(f"{i+1:03d}.jpg", img)
                            
                            m_zip.writestr(f"{sanitize_filename(label)}.cbz", cbz_buf.getvalue())
                    
                    # Simpan hasil per batch ke session state
                    ch_start = batch[0].replace("Ch ", "")
                    ch_end = batch[-1].replace("Ch ", "")
                    
                    st.session_state.dl_list.append({
                        "filename": f"{sanitize_filename(m['title'])}_Ch{ch_start}-{ch_end}.zip",
                        "data": batch_zip_io.getvalue(),
                        "label": f"📥 SIMPAN CHAPTER {ch_start} - {ch_end}"
                    })
                    pbar.progress((b_idx + 1) / len(batches))

                status_text.success("✅ Semua file berhasil dibuat!")
                st.rerun() # PAKSA REFRESH AGAR TOMBOL MUNCUL

            except Exception as e:
                st.error(f"Error: {e}")

    # --- DAFTAR TOMBOL DOWNLOAD (MUNCUL DI SINI) ---
    if st.session_state.dl_list:
        st.markdown("<hr>", unsafe_allow_html=True)
        st.subheader("📁 Hasil Build (Siap Download):")
        for item in st.session_state.dl_list:
            st.download_button(
                label=item["label"],
                data=item["data"],
                file_name=item["filename"],
                mime="application/zip",
                use_container_width=True
            )

st.markdown("<br><p style='text-align: center; color: #697565; font-size: 11px;'>Optimized Batch Downloader (5 Ch / ZIP)</p>", unsafe_allow_html=True)
