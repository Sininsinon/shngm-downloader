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
