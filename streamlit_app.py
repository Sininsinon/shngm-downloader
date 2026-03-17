import streamlit as st
import requests
from io import BytesIO
import zipfile
import re
import concurrent.futures

# --- CONFIG ---
st.set_page_config(page_title="SHNGM Downloader", page_icon="📖", layout="centered")

# --- CSS ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    .stApp { background-color: #181C14 !important; color: #ECDFCC !important; font-family: 'Inter', sans-serif !important; }
    .stTextInput input, .stNumberInput input, .stSelectbox div[data-baseweb="select"] { 
        background-color: #3C3D37 !important; color: #ECDFCC !important; 
        border: 1px solid #697565 !important; border-radius: 10px !important; 
    }
    .stButton > button, .stDownloadButton > button { 
        background-color: #697565 !important; color: #ECDFCC !important; 
        border: 1px solid #697565 !important; border-radius: 10px !important; 
        font-weight: 600 !important; width: 100%; height: auto !important; min-height: 48px !important;
    }
    .manga-card { 
        background-color: #3C3D37; padding: 15px; border-radius: 12px; 
        border-left: 5px solid #697565; margin-bottom: 20px; 
    }
    .guide-box {
        background-color: #2E3025; padding: 15px; border-radius: 10px;
        border: 1px dashed #697565; margin-bottom: 20px; font-size: 14px;
    }
    div[data-testid="stProgress"] > div > div > div > div { background-color: #ECDFCC !important; }
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
if 'processing' not in st.session_state: st.session_state.processing = False

# --- UI ---
st.markdown("<h1 style='text-align: center;'>📖 SHNGM</h1>", unsafe_allow_html=True)

# Hanya tampilkan input jika tidak sedang memproses
if not st.session_state.processing:
    st.markdown("<div class='guide-box'>Salin ID dari URL setelah <code>/series/</code></div>", unsafe_allow_html=True)
    
    col_in, col_sr = st.columns([3, 1])
    m_id = col_in.text_input("Manga ID", placeholder="Tempel ID di sini...", label_visibility="collapsed")

    if col_sr.button("🔍 CARI"):
        if m_id:
            try:
                with st.spinner("Cek data..."):
                    m_res = requests.get(f"https://api.shngm.io/v1/manga/detail/{m_id}", headers=HEADERS).json()
                    if "data" in m_res:
                        c_res = requests.get(f"https://api.shngm.io/v1/chapter/{m_id}/list?page=1&page_size=1500", headers=HEADERS).json()
                        chapters = sorted(c_res["data"], key=lambda x: float(x['chapter_number']))
                        st.session_state.manga_data = {
                            "title": m_res["data"]["title"],
                            "raw": chapters,
                            "map": {f"Ch {c['chapter_number']}": c["chapter_id"] for c in chapters}
                        }
                        st.session_state.dl_list = []
                    else: st.error("ID tidak ditemukan.")
            except: st.error("Koneksi bermasalah.")

# --- SELEKSI CHAPTER ---
if st.session_state.manga_data and not st.session_state.processing:
    m = st.session_state.manga_data
    st.markdown(f"<div class='manga-card'><b>{m['title']}</b></div>", unsafe_allow_html=True)

    mode = st.radio("Mode Pilih:", ["Manual", "Batch"], horizontal=True)
    selected = []
    
    if mode == "Manual":
        current_labels = [f"Ch {c['chapter_number']}" for c in m['raw']]
        selected = st.multiselect("Pilih Chapter:", current_labels)
    else:
        nums = [float(c['chapter_number']) for c in m['raw']]
        c1, c2 = st.columns(2)
        s_ch = c1.number_input("Mulai:", min_value=min(nums), value=min(nums))
        e_ch = c2.number_input("Sampai:", min_value=min(nums), value=max(nums))
        selected = [f"Ch {c['chapter_number']}" for c in m['raw'] if s_ch <= float(c['chapter_number']) <= e_ch]

    if st.button("🚀 PROSES SEKARANG", type="primary"):
        if selected:
            st.session_state.processing = True
            st.session_state.selected_to_process = selected
            st.rerun()
        else:
            st.warning("Pilih chapter dulu!")

# --- LOGIKA PROSES (DILUAR BUTTON AGAR TIDAK BLANK) ---
if st.session_state.processing:
    st.info("⏳ Sedang memproses... Jangan tutup halaman ini.")
    m = st.session_state.manga_data
    selected = st.session_state.selected_to_process
    
    pbar = st.progress(0)
    status = st.empty()
    
    sorted_sel = sorted(selected, key=extract_number)
    batches = [sorted_sel[i:i + 5] for i in range(0, len(sorted_sel), 5)]
    
    try:
        new_dl_list = []
        for idx, batch in enumerate(batches):
            status.markdown(f"📦 Menyiapkan Batch {idx+1}/{len(batches)}...")
            batch_io = BytesIO()
            with zipfile.ZipFile(batch_io, "w") as m_zip:
                for label in batch:
                    # Ambil Chapter Detail
                    res_ch = requests.get(f"https://api.shngm.io/v1/chapter/detail/{m['map'][label]}", headers=HEADERS).json()["data"]
                    urls = [res_ch["base_url"] + res_ch["chapter"]["path"] + img for img in res_ch["chapter"]["data"]]
                    
                    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as ex:
                        imgs = list(ex.map(fetch_image, urls))

                    cbz_io = BytesIO()
                    with zipfile.ZipFile(cbz_io, "w") as c_zip:
                        for i, img in enumerate(imgs):
                            if img: c_zip.writestr(f"{i+1:03d}.jpg", img)
                    m_zip.writestr(f"{sanitize_filename(label)}.cbz", cbz_io.getvalue())
            
            l_start = batch[0].replace("Ch ", "")
            l_end = batch[-1].replace("Ch ", "")
            new_dl_list.append({
                "filename": f"{sanitize_filename(m['title'])}_Ch{l_start}-{l_end}.zip",
                "data": batch_io.getvalue()
            })
            pbar.progress((idx + 1) / len(batches))
        
        st.session_state.dl_list = new_dl_list
        st.session_state.processing = False
        st.success("Selesai!")
        st.rerun() # Refresh untuk menampilkan tombol download
    except Exception as e:
        st.error(f"Error: {e}")
        st.session_state.processing = False
        if st.button("Kembali"): st.rerun()

# --- TAMPILAN DOWNLOAD ---
if st.session_state.dl_list and not st.session_state.processing:
    st.markdown("---")
    st.subheader("📁 Hasil Download")
    
    options = [item["filename"] for item in st.session_state.dl_list]
    choice = st.selectbox("Pilih Batch untuk Download:", options)
    
    final_item = next(item for item in st.session_state.dl_list if item["filename"] == choice)
    
    st.download_button(
        label=f"📥 Download {choice}",
        data=final_item["data"],
        file_name=choice,
        mime="application/zip",
        use_container_width=True
    )
    
    if st.button("❌ Bersihkan / Cari Baru"):
        st.session_state.manga_data = None
        st.session_state.dl_list = []
        st.rerun()

st.markdown("<p style='text-align: center; color: #697565; font-size: 10px; margin-top: 50px;'>Anti-Blank Version</p>", unsafe_allow_html=True)
