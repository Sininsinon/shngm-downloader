import streamlit as st
import requests
from io import BytesIO
import zipfile
import re
import concurrent.futures

# --- CONFIG ---
st.set_page_config(page_title="SHNGM Downloader", page_icon="📖", layout="centered")

# --- CUSTOM CSS (PALET WARNA: #181C14, #3C3D37, #697565, #ECDFCC) ---
st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    
    .stApp {{ background-color: #181C14 !important; color: #ECDFCC !important; font-family: 'Inter', sans-serif !important; }}
    
    /* Input & Number Field */
    .stTextInput input, .stNumberInput input {{ 
        background-color: #3C3D37 !important; 
        color: #ECDFCC !important; 
        border: 1px solid #697565 !important; 
        border-radius: 10px !important; 
    }}

    /* Tombol Utama */
    .stButton > button {{ 
        background-color: #697565 !important; 
        color: #ECDFCC !important; 
        border-radius: 10px !important; 
        border: none !important; 
        font-weight: 600 !important;
        transition: 0.3s;
        width: 100%;
    }}
    .stButton > button:hover {{ background-color: #ECDFCC !important; color: #181C14 !important; }}

    /* Card Box */
    .manga-card {{ 
        background-color: #3C3D37; 
        padding: 15px; 
        border-radius: 12px; 
        border-left: 5px solid #697565; 
        margin-bottom: 20px; 
    }}

    /* PERBAIKAN TOMBOL DOWNLOAD AGAR TIDAK TABRAKAN */
    .stDownloadButton > button {{ 
        background-color: #697565 !important; 
        color: #181C14 !important; 
        font-size: 14px !important; 
        font-weight: 700 !important; 
        line-height: 1.4 !important;
        padding: 12px 10px !important;
        height: auto !important; /* Biar fleksibel kalau teks panjang */
        min-height: 50px !important;
        border: 2px solid #697565 !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.2) !important;
        margin-bottom: 10px !important;
        display: block !important;
        white-space: normal !important; /* Izinkan teks pindah baris kalau sempit */
    }}

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

# --- STATE ---
if 'manga_data' not in st.session_state: st.session_state.manga_data = None
if 'dl_list' not in st.session_state: st.session_state.dl_list = []

# --- UI ---
st.markdown("<h1 style='text-align: center; margin-bottom: 0;'>📖 SHNGM</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #697565; margin-bottom: 20px;'>Manga Downloader • Chunks Edition</p>", unsafe_allow_html=True)

col_in, col_sr = st.columns([3, 1])
m_id = col_in.text_input("ID Manga", placeholder="Input ID...", label_visibility="collapsed")

if col_sr.button("🔍 CARI"):
    try:
        with st.spinner("Wait..."):
            m_res = requests.get(f"https://api.shngm.io/v1/manga/detail/{m_id}", headers=HEADERS).json()
            c_res = requests.get(f"https://api.shngm.io/v1/chapter/{m_id}/list?page=1&page_size=1500", headers=HEADERS).json()
            chapters_sorted = sorted(c_res["data"], key=lambda x: float(x['chapter_number']))
            st.session_state.manga_data = {
                "title": m_res["data"]["title"],
                "raw_chapters": chapters_sorted, 
                "map": {f"Ch {c['chapter_number']}": c["chapter_id"] for c in chapters_sorted}
            }
            st.session_state.dl_list = []
            st.rerun()
    except: st.error("ID tidak valid!")

if st.session_state.manga_data:
    m = st.session_state.manga_data
    st.markdown(f"<div class='manga-card'><small style='color:#697565'>Judul Manga:</small><br><b>{m['title']}</b></div>", unsafe_allow_html=True)

    mode = st.radio("Metode Seleksi:", ["Manual", "Batch (Rentang)"], horizontal=True)
    
    selected_labels = []
    if mode == "Manual":
        order = st.radio("Urutan:", ["Ascending", "Descending"], horizontal=True)
        is_desc = (order == "Descending")
        current_labels = [f"Ch {c['chapter_number']}" for c in sorted(m['raw_chapters'], key=lambda x: float(x['chapter_number']), reverse=is_desc)]
        
        c1, c2 = st.columns(2)
        if c1.button("Pilih Semua"): st.session_state.msel = current_labels
        if c2.button("Hapus Semua"): st.session_state.msel = []
        selected_labels = st.multiselect("Pilih Chapter:", current_labels, key="msel")
    else:
        nums = [float(c['chapter_number']) for c in m['raw_chapters']]
        col_b1, col_b2 = st.columns(2)
        start_ch = col_b1.number_input("Mulai Ch:", min_value=min(nums), max_value=max(nums), value=min(nums))
        end_ch = col_b2.number_input("Sampai Ch:", min_value=min(nums), max_value=max(nums), value=max(nums))
        selected_labels = [f"Ch {c['chapter_number']}" for c in m['raw_chapters'] if start_ch <= float(c['chapter_number']) <= end_ch]
        st.info(f"💡 {len(selected_labels)} Chapter terpilih")

    # --- PROCESS ---
    if st.button("🚀 PROSES SEKARANG", type="primary"):
        if not selected_labels:
            st.warning("Pilih chapter dulu!")
        else:
            st.session_state.dl_list = []
            sorted_sel = sorted(selected_labels, key=extract_number)
            
            # Batch 5 chapter
            batch_size = 5
            batches = [sorted_sel[i:i + batch_size] for i in range(0, len(sorted_sel), batch_size)]
            
            pbar = st.progress(0)
            st_text = st.empty()

            try:
                for b_idx, batch in enumerate(batches):
                    batch_zip_io = BytesIO()
                    with zipfile.ZipFile(batch_zip_io, "w") as m_zip:
                        for label in batch:
                            st_text.markdown(f"⏳ **Batch {b_idx+1}:** Memproses `{label}`...")
                            ch_id = m['map'][label]
                            res_ch = requests.get(f"https://api.shngm.io/v1/chapter/detail/{ch_id}", headers=HEADERS).json()["data"]
                            urls = [res_ch["base_url"] + res_ch["chapter"]["path"] + img for img in res_ch["chapter"]["data"]]

                            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
                                imgs = list(ex.map(fetch_image, urls))

                            cbz_buf = BytesIO()
                            with zipfile.ZipFile(cbz_buf, "w") as c_zip:
                                for i, img in enumerate(imgs):
                                    if img: c_zip.writestr(f"{i+1:03d}.jpg", img)
                            m_zip.writestr(f"{sanitize_filename(label)}.cbz", cbz_buf.getvalue())
                    
                    # Simpan per Batch
                    label_start = batch[0].replace("Ch ", "")
                    label_end = batch[-1].replace("Ch ", "")
                    
                    st.session_state.dl_list.append({
                        "filename": f"{sanitize_filename(m['title'])}_Ch{label_start}-{label_end}.zip",
                        "data": batch_zip_io.getvalue(),
                        "label": f"📂 Download Ch. {label_start} - {label_end}"
                    })
                    pbar.progress((b_idx + 1) / len(batches))

                st_text.success("✅ Selesai! Klik tombol di bawah:")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

    # --- DOWNLOAD BUTTONS ---
    if st.session_state.dl_list:
        st.markdown("<hr>", unsafe_allow_html=True)
        for item in st.session_state.dl_list:
            st.download_button(
                label=item["label"],
                data=item["data"],
                file_name=item["filename"],
                mime="application/zip",
                use_container_width=True
            )

st.markdown("<br><p style='text-align: center; color: #697565; font-size: 11px;'>Simple • Fast • Reliable</p>", unsafe_allow_html=True)
