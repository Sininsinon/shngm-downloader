import streamlit as st
import requests
from io import BytesIO
import zipfile
import re
import concurrent.futures

# --- CONFIG ---
st.set_page_config(page_title="SHNGM Downloader", page_icon="📖", layout="centered")

# --- JAVASCRIPT: PENCEGAHAN REFRESH (WINDOW PARENT) ---
# Menggunakan window.parent karena Streamlit sering berjalan di dalam iframe
st.markdown("""
    <script>
    var warning = function (e) {
        e.preventDefault();
        e.returnValue = '';
    };
    window.parent.addEventListener('beforeunload', warning);
    window.addEventListener('beforeunload', warning);
    </script>
    """, unsafe_allow_html=True)

# --- CSS: WARNA #181C14, #3C3D37, #697565, #ECDFCC ---
st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    
    .stApp {{ background-color: #181C14 !important; color: #ECDFCC !important; font-family: 'Inter', sans-serif !important; }}
    
    /* Input Style */
    .stTextInput input, .stNumberInput input {{ 
        background-color: #3C3D37 !important; color: #ECDFCC !important; 
        border: 1px solid #697565 !important; border-radius: 10px !important; 
    }}

    /* Tombol Style: Dasar #697565 | Hover: #3C3D37 */
    .stButton > button, .stDownloadButton > button {{ 
        background-color: #697565 !important; color: #ECDFCC !important; 
        border: 1px solid #697565 !important; border-radius: 10px !important; 
        font-weight: 600 !important; transition: 0.3s; width: 100%;
        height: auto !important; min-height: 48px !important; padding: 10px !important;
        white-space: normal !important; display: block !important;
    }}
    .stButton > button:hover, .stDownloadButton > button:hover {{ 
        background-color: #3C3D37 !important; border: 1px solid #ECDFCC !important;
        transform: translateY(-2px);
    }}

    .manga-card {{ 
        background-color: #3C3D37; padding: 15px; border-radius: 12px; 
        border-left: 5px solid #697565; margin-bottom: 20px; 
    }}
    
    div[data-testid="stProgress"] > div > div > div > div {{ background-color: #ECDFCC !important; }}
    h1, h2, h3, p, label {{ color: #ECDFCC !important; }}
    span[data-baseweb="tag"] {{ background-color: #697565 !important; color: #ECDFCC !important; }}
    
    /* Radio Button Color Fix */
    div[data-testid="stRadio"] label p {{ color: #ECDFCC !important; }}
    </style>
    """, unsafe_allow_html=True)

# --- CORE FUNCTIONS ---
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

# --- STATE MANAGEMENT ---
if 'manga_data' not in st.session_state: st.session_state.manga_data = None
if 'dl_list' not in st.session_state: st.session_state.dl_list = []

# --- UI ---
st.title("📖 SHNGM Downloader")

col_in, col_sr = st.columns([3, 1])
m_id = col_in.text_input("Manga ID", placeholder="Masukkan ID Manga...", label_visibility="collapsed")

if col_sr.button("🔍 CARI"):
    if m_id:
        try:
            with st.spinner("Searching..."):
                m_res = requests.get(f"https://api.shngm.io/v1/manga/detail/{m_id}", headers=HEADERS).json()
                if m_res.get("data"):
                    c_res = requests.get(f"https://api.shngm.io/v1/chapter/{m_id}/list?page=1&page_size=1500", headers=HEADERS).json()
                    chapters = sorted(c_res["data"], key=lambda x: float(x['chapter_number']))
                    
                    st.session_state.manga_data = {
                        "title": m_res["data"]["title"],
                        "raw": chapters,
                        "map": {f"Ch {c['chapter_number']}": c["chapter_id"] for c in chapters}
                    }
                    st.session_state.dl_list = []
                else: st.error("ID Manga tidak ditemukan.")
        except: st.error("Gagal terhubung ke API.")

if st.session_state.manga_data:
    m = st.session_state.manga_data
    st.markdown(f"<div class='manga-card'><b>{m['title']}</b></div>", unsafe_allow_html=True)

    mode = st.radio("Mode Pilih:", ["Manual", "Batch"], horizontal=True)
    
    selected = []
    if mode == "Manual":
        order = st.radio("Urutan:", ["Ascending", "Descending"], horizontal=True)
        labels = [f"Ch {c['chapter_number']}" for c in sorted(m['raw'], key=lambda x: float(x['chapter_number']), reverse=(order=="Descending"))]
        c1, c2 = st.columns(2)
        if c1.button("Pilih Semua"): st.session_state.msel = labels
        if c2.button("Hapus Semua"): st.session_state.msel = []
        selected = st.multiselect("Daftar Ch:", labels, key="msel")
    else:
        nums = [float(c['chapter_number']) for c in m['raw']]
        col_b1, col_b2 = st.columns(2)
        s_ch = col_b1.number_input("Mulai:", min_value=min(nums), max_value=max(nums), value=min(nums))
        e_ch = col_b2.number_input("Sampai:", min_value=min(nums), max_value=max(nums), value=max(nums))
        selected = [f"Ch {c['chapter_number']}" for c in m['raw'] if s_ch <= float(c['chapter_number']) <= e_ch]
        st.info(f"💡 {len(selected)} Chapter terpilih")

    if st.button("🚀 PROSES BATCH (5 Ch/ZIP)", type="primary"):
        if not selected:
            st.warning("Pilih chapter!")
        else:
            st.session_state.dl_list = [] 
            sorted_sel = sorted(selected, key=extract_number)
            batches = [sorted_sel[i:i + 5] for i in range(0, len(sorted_sel), 5)]
            
            pbar = st.progress(0)
            st_info = st.empty()

            try:
                for b_idx, batch in enumerate(batches):
                    batch_io = BytesIO()
                    with zipfile.ZipFile(batch_io, "w") as m_zip:
                        for label in batch:
                            st_info.markdown(f"⏳ **Batch {b_idx+1}:** Memproses `{label}`")
                            res_ch = requests.get(f"https://api.shngm.io/v1/chapter/detail/{m['map'][label]}", headers=HEADERS).json()["data"]
                            urls = [res_ch["base_url"] + res_ch["chapter"]["path"] + img for img in res_ch["chapter"]["data"]]
                            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
                                imgs = list(ex.map(fetch_image, urls))
                            cbz_io = BytesIO()
                            with zipfile.ZipFile(cbz_io, "w") as c_zip:
                                for i, img in enumerate(imgs):
                                    if img: c_zip.writestr(f"{i+1:03d}.jpg", img)
                            m_zip.writestr(f"{sanitize_filename(label)}.cbz", cbz_io.getvalue())
                    
                    l_start, l_end = batch[0].replace("Ch ", ""), batch[-1].replace("Ch ", "")
                    st.session_state.dl_list.append({
                        "filename": f"{sanitize_filename(m['title'])}_Ch{l_start}-{l_end}.zip",
                        "data": batch_io.getvalue(),
                        "label": f"📂 Download Chapter {l_start} - {l_end}"
                    })
                    pbar.progress((b_idx + 1) / len(batches))
                st_info.success("✅ Build Selesai!")
            except: st.error("Gangguan saat memproses gambar.")

    # DAFTAR DOWNLOAD (Popup Cepat)
    if st.session_state.dl_list:
        st.markdown("<hr>", unsafe_allow_html=True)
        for idx, item in enumerate(st.session_state.dl_list):
            st.download_button(
                label=item["label"],
                data=item["data"],
                file_name=item["filename"],
                mime="application/zip",
                key=f"dl_{idx}",
                use_container_width=True
            )
