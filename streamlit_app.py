import streamlit as st
import requests
from io import BytesIO
import zipfile
import re
import concurrent.futures
import base64  # Tambahan untuk konversi data

# --- CONFIG ---
st.set_page_config(page_title="SHNGM Downloader", page_icon="📖", layout="centered")

# --- JAVASCRIPT UNTUK AUTO DOWNLOAD ---
def trigger_auto_download(bin_data, file_name):
    # Konversi data biner ke Base64 agar bisa dibaca JavaScript
    b64 = base64.b64encode(bin_data).decode()
    js_code = f"""
        <script>
        var a = document.createElement("a");
        a.href = "data:application/zip;base64,{b64}";
        a.download = "{file_name}";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        </script>
    """
    st.components.v1.html(js_code, height=0)

# --- CSS ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    .stApp { background-color: #181C14 !important; color: #ECDFCC !important; font-family: 'Inter', sans-serif !important; }
    .stTextInput input, .stNumberInput input { 
        background-color: #3C3D37 !important; color: #ECDFCC !important; 
        border: 1px solid #697565 !important; border-radius: 10px !important; 
    }
    .stButton > button { 
        background-color: #697565 !important; color: #ECDFCC !important; 
        border-radius: 10px !important; width: 100%; min-height: 48px !important;
    }
    .guide-box { background-color: #2E3025; padding: 15px; border-radius: 10px; border: 1px dashed #697565; margin-bottom: 20px; font-size: 14px; }
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
        r = requests.get(url, headers=HEADERS, timeout=15)
        return r.content if r.status_code == 200 else None
    except: return None

# --- STATE MANAGEMENT ---
if 'manga_data' not in st.session_state: st.session_state.manga_data = None
if 'last_zip' not in st.session_state: st.session_state.last_zip = None

# --- UI ---
st.markdown("<h1 style='text-align: center;'>📖 SHNGM</h1>", unsafe_allow_html=True)

st.markdown("""
<div class='guide-box'>
    <b>Cara Pakai:</b> Tempel ID, pilih chapter, klik Mulai. <br>
    Sistem akan memproses dan <b>otomatis</b> memicu download di browser Anda.
</div>
""", unsafe_allow_html=True)

m_id = st.text_input("Manga ID", placeholder="Tempel ID...", label_visibility="collapsed")

if st.button("🔍 CARI KOMIK"):
    if m_id:
        try:
            m_res = requests.get(f"https://api.shngm.io/v1/manga/detail/{m_id}", headers=HEADERS).json()
            c_res = requests.get(f"https://api.shngm.io/v1/chapter/{m_id}/list?page=1&page_size=1500", headers=HEADERS).json()
            chapters = sorted(c_res["data"], key=lambda x: float(x['chapter_number']))
            st.session_state.manga_data = {"title": m_res["data"]["title"], "raw": chapters, "map": {f"Ch {c['chapter_number']}": c["chapter_id"] for c in chapters}}
        except: st.error("Gagal ambil data.")

if st.session_state.manga_data:
    m = st.session_state.manga_data
    st.write(f"Komik: **{m['title']}**")
    
    nums = [float(c['chapter_number']) for c in m['raw']]
    c1, c2 = st.columns(2)
    s_ch = c1.number_input("Mulai:", min_value=min(nums), value=min(nums))
    e_ch = c2.number_input("Sampai:", min_value=min(nums), value=max(nums))
    
    selected = [f"Ch {c['chapter_number']}" for c in m['raw'] if s_ch <= float(c['chapter_number']) <= e_ch]

    if st.button("🚀 MULAI PROSES & DOWNLOAD", type="primary"):
        if selected:
            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as m_zip:
                pbar = st.progress(0)
                for i, label in enumerate(selected):
                    res_ch = requests.get(f"https://api.shngm.io/v1/chapter/detail/{m['map'][label]}", headers=HEADERS).json()["data"]
                    urls = [res_ch["base_url"] + res_ch["chapter"]["path"] + img for img in res_ch["chapter"]["data"]]
                    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as ex:
                        imgs = list(ex.map(fetch_image, urls))
                    
                    cbz_io = BytesIO()
                    with zipfile.ZipFile(cbz_io, "w") as c_zip:
                        for idx, img in enumerate(imgs):
                            if img: c_zip.writestr(f"{idx+1:03d}.jpg", img)
                    m_zip.writestr(f"{sanitize_filename(label)}.cbz", cbz_io.getvalue())
                    pbar.progress((i + 1) / len(selected))

            file_name = f"{sanitize_filename(m['title'])}_Batch.zip"
            final_data = zip_buffer.getvalue()
            
            # --- ACTION: OTOMATIS DOWNLOAD ---
            st.success("Proses Selesai! Browser akan otomatis menyimpan file.")
            trigger_auto_download(final_data, file_name)
