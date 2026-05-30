import streamlit as st
import requests
from io import BytesIO
import zipfile
import re
import concurrent.futures
import os
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- CONFIG ---
st.set_page_config(page_title="SHNGM Downloader", page_icon="📖", layout="centered")

# --- CSS & JAVASCRIPT (ANTI-SLEEP) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    .stApp { background-color: #181C14 !important; color: #ECDFCC !important; font-family: 'Inter', sans-serif !important; }
    
    /* Input Style */
    .stTextInput input, .stNumberInput input, .stSelectbox div[data-baseweb="select"] { 
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

# Setup Session dengan Retry
def get_session():
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

http_session = get_session()

def sanitize_filename(name):
    # Dibiarkan menggunakan spasi agar nama file lebih rapi
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()

def extract_number(text):
    nums = re.findall(r"(\d+\.?\d*)", str(text))
    return float(nums[0]) if nums else 0.0

def fetch_image(url):
    try:
        r = http_session.get(url, headers=HEADERS, timeout=20)
        return r.content if r.status_code == 200 else None
    except: 
        return None

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
    total_chapters = len(m['raw']) 
    
    st.markdown(f"""
        <div class='manga-card'>
            <small style='color:#697565'>Judul Terdeteksi:</small><br>
            <b>{m['title']}</b><br><br>
            <small style='color:#697565'>Total Chapter Tersedia:</small><br>
            <b>{total_chapters} Chapter</b>
        </div>
    """, unsafe_allow_html=True)

    mode = st.radio("Mode Pilih:", ["Manual", "Batch (Rentang)", "Paket (Per 20 Ch)"], horizontal=True)
    
    selected = []
    if mode == "Manual":
        order = st.radio("Urutan:", ["Ascending", "Descending"], horizontal=True)
        current_labels = [f"Ch {c['chapter_number']}" for c in sorted(m['raw'], key=lambda x: float(x['chapter_number']), reverse=(order=="Descending"))]
        
        c1, c2 = st.columns(2)
        if c1.button("Pilih Semua"): st.session_state.msel = current_labels
        if c2.button("Hapus Semua"): st.session_state.msel = []
        selected = st.multiselect("Pilih Chapter:", current_labels, key="msel")
        
    elif mode == "Batch (Rentang)":
        nums = [float(c['chapter_number']) for c in m['raw']]
        col_b1, col_b2 = st.columns(2)
        s_ch = col_b1.number_input("Mulai Ch:", min_value=min(nums), max_value=max(nums), value=min(nums))
        e_ch = col_b2.number_input("Sampai Ch:", min_value=min(nums), max_value=max(nums), value=max(nums))
        selected = [f"Ch {c['chapter_number']}" for c in m['raw'] if s_ch <= float(c['chapter_number']) <= e_ch]
        st.info(f"💡 {len(selected)} Chapter terpilih")
        
    else: 
        sorted_raw = sorted(m['raw'], key=lambda x: float(x['chapter_number']))
        chunked_20 = [sorted_raw[i:i + 20] for i in range(0, len(sorted_raw), 20)]
        
        preset_options = []
        preset_mapping = {}
        for chunk in chunked_20:
            start = chunk[0]['chapter_number']
            end = chunk[-1]['chapter_number']
            label = f"Chapter {start} - {end} ({len(chunk)} chapter)"
            preset_options.append(label)
            preset_mapping[label] = [f"Ch {c['chapter_number']}" for c in chunk]
            
        p_sel = st.selectbox("Pilih Paket Download:", preset_options)
        if p_sel:
            selected = preset_mapping[p_sel]
            jml_zip = (len(selected) // 5) + (1 if len(selected) % 5 != 0 else 0)
            st.info(f"💡 Memilih {len(selected)} chapter. Akan dipecah menjadi {jml_zip} file ZIP.")

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
                    if not os.path.exists("static"):
                        os.makedirs("static")

                    # Penyiapan judul ZIP agar aman
                    safe_title_zip = sanitize_filename(m['title'])
                    if len(safe_title_zip) > 40:
                        safe_title_zip = safe_title_zip[:40].strip()

                    for b_idx, batch in enumerate(batches):
                        l_start = extract_number(batch[0])
                        l_end = extract_number(batch[-1])
                        
                        # Format angka untuk nama file ZIP (misal: Ch 01-05)
                        str_start = f"{int(l_start):02d}" if l_start.is_integer() else str(l_start)
                        str_end = f"{int(l_end):02d}" if l_end.is_integer() else str(l_end)
                        
                        file_name = f"{safe_title_zip} - Ch {str_start}-{str_end}.zip"
                        zip_path = os.path.join("static", file_name) 

                        with zipfile.ZipFile(zip_path, "w") as m_zip:
                            for label in batch:
                                st_info.markdown(f"⏳ Memproses: `{label}`")
                                res_ch = requests.get(f"https://api.shngm.io/v1/chapter/detail/{m['map'][label]}", headers=HEADERS).json()["data"]
                                urls = [res_ch["base_url"] + res_ch["chapter"]["path"] + img for img in res_ch["chapter"]["data"]]
                                
                                with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
                                    imgs = list(ex.map(fetch_image, urls))

                                cbz_io = BytesIO()
                                with zipfile.ZipFile(cbz_io, "w") as c_zip:
                                    for i, img in enumerate(imgs):
                                        if img: c_zip.writestr(f"{i+1:03d}.jpg", img)
                                
                                # PEMBUATAN NAMA FILE CBZ (Format: C01 - Judul Manga.cbz)
                                angka_ch = extract_number(label)
                                str_ch = f"{int(angka_ch):02d}" if angka_ch.is_integer() else str(angka_ch)
                                format_label = f"C{str_ch}"
                                
                                nama_cbz = f"{format_label} - {safe_title_zip}.cbz"
                                
                                m_zip.writestr(nama_cbz, cbz_io.getvalue())
                        
                        st.session_state.dl_list.append({
                            "filename": file_name,
                            "path": zip_path,
                            "label": f"📂 Download Ch {str_start} - {str_end}"
                        })
                        pbar.progress((b_idx + 1) / len(batches))
                    
                    st_info.success("✅ Semua paket selesai diproses!")
                except Exception as e:
                    st.error(f"Terjadi kesalahan saat build: {e}")

    if st.session_state.dl_list:
        st.markdown("<hr>", unsafe_allow_html=True)
        st.subheader("📁 Hasil Download:")
        for item in st.session_state.dl_list:
            if os.path.exists(item["path"]):
                # Mengganti spasi dengan %20 agar URL HTML valid
                safe_url_name = item['filename'].replace(" ", "%20")
                file_url = f"app/static/{safe_url_name}"
                
                html_button = f"""
                <a href="{file_url}" download="{item['filename']}" style="text-decoration: none;">
                    <button style="width: 100%; background-color: #697565; color: #ECDFCC; border: none; 
                                   border-radius: 10px; font-weight: 600; padding: 12px; margin-bottom: 10px; 
                                   cursor: pointer; transition: 0.3s; font-family: 'Inter', sans-serif;">
                        {item['label']}
                    </button>
                </a>
                """
                st.markdown(html_button, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🗑️ Bersihkan Server & Mulai Baru", type="secondary"):
            for item in st.session_state.dl_list:
                if os.path.exists(item["path"]):
                    os.remove(item["path"])
            st.session_state.dl_list = []
            st.rerun()

st.markdown("<br><p style='text-align: center; color: #697565; font-size: 11px;'>Simple • Fast • No Sleep Mode Active</p>", unsafe_allow_html=True)
