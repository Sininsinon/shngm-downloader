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
    .stApp {{ background-color: #181C14 !important; color: #ECDFCC !important; font-family: 'Inter', sans-serif !important; }}
    .stTextInput input, .stNumberInput input {{ background-color: #3C3D37 !important; color: #ECDFCC !important; border: 1px solid #697565 !important; border-radius: 12px !important; height: 48px !important; }}
    .stButton > button {{ background-color: #697565 !important; color: #ECDFCC !important; border-radius: 12px !important; border: none !important; font-weight: 600 !important; height: 48px !important; transition: all 0.2s ease !important; }}
    .stButton > button:hover {{ background-color: #ECDFCC !important; color: #181C14 !important; }}
    .manga-card {{ background-color: #3C3D37; padding: 20px; border-radius: 16px; border: 1px solid #697565; margin-bottom: 20px; text-align: center; }}
    .sub-btn .stButton > button {{ height: 38px !important; font-size: 13px !important; background-color: #3C3D37 !important; border: 1px solid #697565 !important; }}
    .stDownloadButton > button {{ background-color: #ECDFCC !important; color: #181C14 !important; height: 52px !important; font-size: 15px !important; margin-bottom: 12px !important; border: 2px solid #697565 !important; }}
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

# --- UI CONTENT ---
st.markdown("<h1 style='text-align: center;'>📖 SHNGM <span style='color: #697565;'>Downloader</span></h1>", unsafe_allow_html=True)

if 'manga_data' not in st.session_state: st.session_state.manga_data = None
if 'dl_list' not in st.session_state: st.session_state.dl_list = []

# SEARCH BAR
col_in, col_sr = st.columns([3, 1])
m_id = col_in.text_input("ID Manga", placeholder="Masukkan ID...", label_visibility="collapsed")

if col_sr.button("🔍 CARI", use_container_width=True):
    try:
        with st.spinner("Loading..."):
            m_res = requests.get(f"https://api.shngm.io/v1/manga/detail/{m_id}", headers=HEADERS).json()
            c_res = requests.get(f"https://api.shngm.io/v1/chapter/{m_id}/list?page=1&page_size=1500", headers=HEADERS).json()
            # Sortir data asli secara ascending untuk keperluan batch
            chapters_sorted = sorted(c_res["data"], key=lambda x: float(x['chapter_number']))
            st.session_state.manga_data = {
                "title": m_res["data"]["title"],
                "raw_chapters": chapters_sorted, 
                "map": {f"Ch {c['chapter_number']}": c["chapter_id"] for c in chapters_sorted}
            }
            st.session_state.dl_list = []
    except: st.error("ID Tidak ditemukan!")

if st.session_state.manga_data:
    m = st.session_state.manga_data
    st.markdown(f"<div class='manga-card'><h2>{m['title']}</h2></div>", unsafe_allow_html=True)

    # --- FITUR MODE SELEKSI ---
    mode = st.radio("Mode Seleksi:", ["Manual", "Batch (Rentang)"], horizontal=True)
    
    selected_labels = []

    if mode == "Manual":
        order = st.radio("Urutan List:", ["Ascending", "Descending"], horizontal=True)
        is_desc = (order == "Descending")
        current_labels = [f"Ch {c['chapter_number']}" for c in sorted(m['raw_chapters'], key=lambda x: float(x['chapter_number']), reverse=is_desc)]
        
        st.markdown('<div class="sub-btn">', unsafe_allow_html=True)
        c1, c2, _ = st.columns([1, 1, 1])
        if c1.button("Pilih Semua"): st.session_state.sel_ch_manual = current_labels
        if c2.button("Hapus Semua"): st.session_state.sel_ch_manual = []
        st.markdown('</div>', unsafe_allow_html=True)
        
        selected_labels = st.multiselect("Pilih Chapter:", current_labels, key="sel_ch_manual")

    else:
        # Mode Batch Range
        all_nums = [float(c['chapter_number']) for c in m['raw_chapters']]
        c_min, c_max = min(all_nums), max(all_nums)
        
        col_b1, col_b2 = st.columns(2)
        start_ch = col_b1.number_input("Dari Chapter:", min_value=c_min, max_value=c_max, value=c_min, step=1.0)
        end_ch = col_b2.number_input("Sampai Chapter:", min_value=c_min, max_value=c_max, value=min(start_ch + 9, c_max), step=1.0)
        
        # Ambil label yang masuk dalam rentang
        selected_labels = [f"Ch {c['chapter_number']}" for c in m['raw_chapters'] if start_ch <= float(c['chapter_number']) <= end_ch]
        st.info(f"💡 Total {len(selected_labels)} chapter terpilih dalam rentang ini.")

    # --- PROSES DOWNLOAD ---
    if st.button("🚀 MULAI PROSES", use_container_width=True):
        if not selected_labels:
            st.warning("Pilih chapter atau tentukan rentang dulu!")
        else:
            st.session_state.dl_list = []
            sorted_sel = sorted(selected_labels, key=extract_number)
            
            # Pembagian 5 chapter per batch
            batch_size = 5
            batches = [sorted_sel[i:i + batch_size] for i in range(0, len(sorted_sel), batch_size)]
            
            total_ch = len(sorted_sel)
            count = 0
            pbar = st.progress(0)
            status = st.empty()

            try:
                for b_idx, batch in enumerate(batches):
                    batch_zip = BytesIO()
                    with zipfile.ZipFile(batch_zip, "w") as m_zip:
                        for label in batch:
                            status.markdown(f"⏳ **Batch {b_idx+1}** - Processing: `{label}`")
                            ch_id = m['map'][label]
                            res = requests.get(f"https://api.shngm.io/v1/chapter/detail/{ch_id}", headers=HEADERS).json()["data"]
                            urls = [res["base_url"] + res["chapter"]["path"] + img for img in res["chapter"]["data"]]

                            with concurrent.futures.ThreadPoolExecutor(max_workers=15) as ex:
                                imgs = list(ex.map(fetch_image, urls))

                            cbz_buf = BytesIO()
                            with zipfile.ZipFile(cbz_buf, "w") as c_zip:
                                for i, img in enumerate(imgs):
                                    if img: c_zip.writestr(f"{i+1:03d}.jpg", img)
                            m_zip.writestr(f"{sanitize_filename(label)}.cbz", cbz_buf.getvalue())
                            count += 1
                            pbar.progress(count / total_ch)
                    
                    file_range = f"{batch[0]}-{batch[-1]}"
                    st.session_state.dl_list.append({
                        "filename": f"{sanitize_filename(m['title'])}_{file_range}.zip",
                        "data": batch_zip.getvalue(),
                        "label": f"📥 DOWNLOAD {file_range}"
                    })
                status.success(f"✅ Selesai! {len(batches)} File ZIP siap diunduh.")
            except Exception as e:
                st.error(f"Error: {e}")

    # TAMPILKAN TOMBOL DOWNLOAD
    if st.session_state.dl_list:
        st.markdown("<hr>", unsafe_allow_html=True)
        st.subheader("Daftar File ZIP (Per 5 Ch):")
        for item in st.session_state.dl_list:
            st.download_button(label=item["label"], data=item["data"], file_name=item["filename"], mime="application/zip", use_container_width=True)

st.markdown("<br><p style='text-align: center; color: #697565; font-size: 11px;'>Manual vs Batch Selection Mode • Max 5 Ch/File</p>", unsafe_allow_html=True)
