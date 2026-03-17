import streamlit as st
import requests
from io import BytesIO
import zipfile
import re
import concurrent.futures

# --- CONFIG ---
st.set_page_config(page_title="SHNGM Downloader", page_icon="📖", layout="centered")

# --- CSS & JAVASCRIPT (ANTI-SLEEP) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    .stApp { background-color: #181C14 !important; color: #ECDFCC !important; font-family: 'Inter', sans-serif !important; }
    
    /* Input Style */
    .stTextInput input, .stNumberInput input { 
        background-color: #3C3D37 !important; color: #ECDFCC !important; 
        border: 1px solid #697565 !important; border-radius: 10px !important; 
    }

    /* Tombol Style */
    .stButton > button, .stDownloadButton > button { 
        background-color: #697565 !important; color: #ECDFCC !important; 
        border: 1px solid #697565 !important; border-radius: 10px !important; 
        font-weight: 600 !important; transition: 0.3s; width: 100%;
        height: auto !important; min-height: 48px !important; padding: 10px !important;
        white-space: normal !important; display: block !important;
    }
    .stButton > button:hover, .stDownloadButton > button:hover { 
        background-color: #3C3D37 !important; border: 1px solid #ECDFCC !important;
        transform: translateY(-2px);
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
    h1, h2, h3, p, label { color: #ECDFCC !important; }
    </style>

    <script>
    // ANTI-SLEEP SCRIPT
    let wakeLock = null;
    const requestWakeLock = async () => {
      try {
        wakeLock = await navigator.wakeLock.request('screen');
      } catch (err) {
        console.error(`${err.name}, ${err.message}`);
      }
    };
    requestWakeLock();
    document.addEventListener('visibilitychange', async () => {
      if (wakeLock !== null && document.visibilityState === 'visible') {
        await requestWakeLock();
      }
    });
    </script>
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
st.markdown("<h1 style='text-align: center;'>📖 SHNGM</h1>", unsafe_allow_html=True)

# --- PANDUAN AMBIL ID ---
st.markdown("""
<div class='guide-box'>
    <b>Cara Mengambil ID Komik:</b><br>
    1. Buka situs <a href='https://c.shinigami.asia' style='color:#697565'>c.shinigami.asia</a> dan pilih komik.<br>
    2. Lihat alamat (URL) komik tersebut di bagian atas browser.<br>
    3. Salin kode unik setelah tulisan <code>/series/</code>.<br>
    <b>Contoh:</b> <code>.../series/b5f07831-f952-4919-af7c-aae4cadeb607</code>
    <b>yang di ambil:</b><code> b5f07831-f952-4919-af7c-aae4cadeb607</code>
</div>
""", unsafe_allow_html=True)

col_in, col_sr = st.columns([3, 1])
m_id = col_in.text_input("Manga ID", placeholder="Tempel ID di sini...", label_visibility="collapsed")

if col_sr.button("🔍 CARI"):
    if m_id:
        try:
            with st.spinner("Mengambil data..."):
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
                else:
                    st.error("ID Manga tidak ditemukan.")
        except Exception as e:
            st.error("Terjadi gangguan koneksi.")

if st.session_state.manga_data:
    m = st.session_state.manga_data
    st.markdown(f"<div class='manga-card'><small style='color:#697565'>Judul Terdeteksi:</small><br><b>{m['title']}</b></div>", unsafe_allow_html=True)

    mode = st.radio("Mode Pilih:", ["Manual", "Batch (Rentang)"], horizontal=True)
    
    selected = []
    if mode == "Manual":
        order = st.radio("Urutan:", ["Ascending", "Descending"], horizontal=True)
        current_labels = [f"Ch {c['chapter_number']}" for c in sorted(m['raw'], key=lambda x: float(x['chapter_number']), reverse=(order=="Descending"))]
        
        c1, c2 = st.columns(2)
        if c1.button("Pilih Semua"): st.session_state.msel = current_labels
        if c2.button("Hapus Semua"): st.session_state.msel = []
        selected = st.multiselect("Pilih Chapter:", current_labels, key="msel")
    else:
        nums = [float(c['chapter_number']) for c in m['raw']]
        col_b1, col_b2 = st.columns(2)
        s_ch = col_b1.number_input("Mulai Ch:", min_value=min(nums), max_value=max(nums), value=min(nums))
        e_ch = col_b2.number_input("Sampai Ch:", min_value=min(nums), max_value=max(nums), value=max(nums))
        selected = [f"Ch {c['chapter_number']}" for c in m['raw'] if s_ch <= float(c['chapter_number']) <= e_ch]
        st.info(f"💡 {len(selected)} Chapter terpilih")

    if st.button("🚀 MULAI PROSES SEKARANG", type="primary"):
        if not selected:
            st.warning("Silahkan pilih chapter!")
        else:
            prog_container = st.container()
            with prog_container:
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
                                st_info.markdown(f"⏳ Memproses: `{label}`")
                                res_ch = requests.get(f"https://api.shngm.io/v1/chapter/detail/{m['map'][label]}", headers=HEADERS).json()["data"]
                                urls = [res_ch["base_url"] + res_ch["chapter"]["path"] + img for img in res_ch["chapter"]["data"]]
                                
                                with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
                                    imgs = list(ex.map(fetch_image, urls))

                                cbz_io = BytesIO()
                                with zipfile.ZipFile(cbz_io, "w") as c_zip:
                                    for i, img in enumerate(imgs):
                                        if img: c_zip.writestr(f"{i+1:03d}.jpg", img)
                                m_zip.writestr(f"{sanitize_filename(label)}.cbz", cbz_io.getvalue())
                        
                        l_start = batch[0].replace("Ch ", "")
                        l_end = batch[-1].replace("Ch ", "")
                        st.session_state.dl_list.append({
                            "filename": f"{sanitize_filename(m['title'])}_Ch{l_start}-{l_end}.zip",
                            "data": batch_io.getvalue(),
                            "label": f"📂 Download Chapter {l_start} - {l_end}"
                        })
                        pbar.progress((b_idx + 1) / len(batches))
                    
                    st_info.success("✅ Proses Selesai!")
                except Exception as e:
                    st.error("Terjadi kesalahan saat build.")

    if st.session_state.dl_list:
        st.markdown("<hr>", unsafe_allow_html=True)
        st.subheader("📁 Hasil Download:")
        for item in st.session_state.dl_list:
            st.download_button(
                label=item["label"],
                data=item["data"],
                file_name=item["filename"],
                mime="application/zip",
                key=item["filename"]
            )

st.markdown("<br><p style='text-align: center; color: #697565; font-size: 11px;'>Simple • Fast • No Sleep Mode Active</p>", unsafe_allow_html=True)
