import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import barcode
from barcode.writer import ImageWriter
import io
import base64
import streamlit.components.v1 as components

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Laju Logistics V5", page_icon="🚚", layout="wide")

# --- STYLE & CSS ---
if 'dark_mode' not in st.session_state: st.session_state['dark_mode'] = False

def local_css():
    if st.session_state['dark_mode']:
        bg_color, text_color, card_bg = "#1a1a2e", "#ffffff", "#16213e"
    else:
        bg_color, text_color, card_bg = "#fdfbf7", "#0f3460", "#ffffff"
    
    st.markdown(f"""
    <style>
    .stApp {{ background-color: {bg_color}; color: {text_color}; }}
    .stButton>button {{ background-color: #e94560; color: white; border-radius: 8px; border: none; width: 100%; }}
    .stButton>button:hover {{ background-color: #c72c41; }}
    div[data-testid="metric-container"] {{ background-color: {card_bg}; border: 1px solid #ddd; padding: 10px; border-radius: 10px; box-shadow: 2px 2px 5px rgba(0,0,0,0.1); }}
    
    /* ANIMASI KERETA */
    @keyframes drive {{ from {{ transform: translateX(-100%); }} to {{ transform: translateX(100%); }} }}
    .train-container {{ width: 100%; overflow: hidden; white-space: nowrap; padding: 10px 0; }}
    .train-icon {{ display: inline-block; font-size: 2.5rem; animation: drive 8s linear infinite; }}
    </style>
    """, unsafe_allow_html=True)

local_css()

# --- KONEKSI DATABASE ---
@st.cache_resource
def get_gspread_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    return gspread.authorize(creds)

def get_data(sheet_name):
    return get_gspread_client().open_by_url(st.secrets["sheets_url"]).worksheet(sheet_name)

# --- HELPER FUNCTIONS ---
def clean_currency(value):
    """Membersihkan format Rp dan koma agar terbaca sebagai angka"""
    try:
        if isinstance(value, (int, float)): return value
        clean_str = str(value).replace("Rp", "").replace(".", "").replace(",", "").strip()
        return float(clean_str) if clean_str else 0
    except:
        return 0

def generate_resi():
    return f"LJ-{datetime.now().strftime('%d%H%M%S')}"

def generate_barcode(resi):
    rv = io.BytesIO()
    barcode.get_barcode_class('code128')(resi, writer=ImageWriter()).write(rv)
    return base64.b64encode(rv.getvalue()).decode()

# --- STATE MANAGEMENT ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'page' not in st.session_state: st.session_state['page'] = 'Login'
if 'form_data' not in st.session_state: st.session_state['form_data'] = {}
if 'show_resi' not in st.session_state: st.session_state['show_resi'] = False
if 'html_resi_cache' not in st.session_state: st.session_state['html_resi_cache'] = ""

# --- HALAMAN 1: LOGIN (DENGAN REKAP OTOMATIS) ---
def login_page():
    st.markdown("<div class='train-container'><div class='train-icon'>🚚 💨 LAJU LOGISTICS 💨 🚚</div></div>", unsafe_allow_html=True)
    st.title("Login Staff Laju")
    
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        with st.form("login"):
            user = st.text_input("Username")
            pw = st.text_input("Password", type="password")
            if st.form_submit_button("Masuk"):
                try:
                    sheet = get_data("User")
                    records = sheet.get_all_records()
                    df = pd.DataFrame(records)
                    
                    # Normalisasi string
                    df['Nama'] = df['Nama'].astype(str).str.strip()
                    df['Password'] = df['Password'].astype(str).str.strip()
                    
                    cek = df[(df['Nama'] == str(user).strip()) & (df['Password'] == str(pw).strip())]
                    
                    if not cek.empty:
                        user_data = cek.iloc[0].to_dict()
                        st.session_state['logged_in'] = True
                        st.session_state['user_info'] = user_data
                        st.session_state['page'] = 'Dashboard'
                        
                        # --- FITUR BARU: CATAT REKAP LOGIN ---
                        try:
                            log_sheet = get_data("Riwayat Login")
                            log_sheet.append_row([str(datetime.now()), user_data['Nama'], user_data['Cabang']])
                        except:
                            pass # Jangan error kalau sheet belum dibuat, tapi idealnya dibuat
                            
                        st.rerun()
                    else:
                        st.error("Username/Password salah!")
                except Exception as e:
                    st.error(f"Error Database: {e}")

# --- HALAMAN 2: DASHBOARD ---
def dashboard_page():
    user = st.session_state['user_info']
    st.write(f"Halo, **{user['Nama']}**! Semangat di Cabang **{user['Cabang']}**.")
    
    try:
        # Ambil Data Active
        df = pd.DataFrame(get_data("Data ( Active )").get_all_records())
        if not df.empty:
            # FIX: Bersihkan data keuangan dulu biar chart muncul
            df['Total_Ongkir_Num'] = df['Total_Ongkir'].apply(clean_currency)
            omzet = df['Total_Ongkir_Num'].sum()
            total = len(df)
            transit = len(df[df['Status'].astype(str).str.contains("Transit")])
        else:
            omzet, total, transit = 0, 0, 0
    except: omzet, total, transit = 0, 0, 0
    
    m1, m2, m3 = st.columns(3)
    m1.metric("📦 Paket Aktif", total)
    m2.metric("🚚 Sedang Transit", transit)
    m3.metric("💰 Omzet Pending", f"Rp {omzet:,.0f}")
    
    st.markdown("### Menu Cepat")
    c1, c2, c3, c4 = st.columns(4)
    if c1.button("Input Baru"): st.session_state['page'] = 'Input'
    if c2.button("Transit/Scan"): st.session_state['page'] = 'Transit'
    if c3.button("Tracking"): st.session_state['page'] = 'Tracking'
    if c4.button("Admin & Laporan"): st.session_state['page'] = 'Admin'

# --- HALAMAN 3: INPUT ---
def input_page():
    st.header("📦 Input Pengiriman")
    st.session_state['show_resi'] = False 

    with st.expander("Data Pengirim & Penerima", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            pengirim = st.text_input("Nama Pengirim", key="s_n")
            hp_pengirim = st.text_input("HP Pengirim", key="s_h")
            alamat_pengirim = st.text_area("Alamat Asal", height=70, key="s_a")
        with c2:
            penerima = st.text_input("Nama Penerima", key="r_n")
            hp_penerima = st.text_input("HP Penerima", key="r_h")
            kota = st.text_input("Kota Tujuan", key="r_k")
            detail = st.text_area("Detail Alamat", height=70, key="r_d")

    st.subheader("Layanan & Biaya")
    col_a, col_b = st.columns(2)
    with col_a:
        berat = st.number_input("Berat (Kg)", 1.0, step=0.5)
        qty = st.number_input("Koli", 1)
        
    with col_b:
        layanan = st.selectbox("Layanan", ["Express", "Cargo", "Makanan"])
        harga_dasar = 17000 if layanan == "Express" else 5000 if layanan == "Makanan" else 4000
        ongkir = max(1, berat) * harga_dasar
        if layanan == "Cargo" and berat < 10: ongkir = 10 * 4000
        
        garansi = 0
        harga_brg = 0
        if st.checkbox("Pakai Garansi?"):
            harga_brg = st.number_input("Harga Barang", 0, step=10000)
            garansi = 5000 if layanan == "Makanan" else harga_brg * 0.005
            st.caption(f"Biaya Garansi: Rp {garansi:,.0f}")

    total = ongkir + garansi
    st.write(f"### Total: Rp {total:,.0f}")
    
    if st.button("Lanjut Bayar ➡️"):
        if not pengirim or not penerima: st.warning("Data belum lengkap!")
        else:
            st.session_state['form_data'] = {
                "Resi": generate_resi(), "Pengirim": pengirim, "HP_Pengirim": hp_pengirim, "Alamat_Pengirim": alamat_pengirim,
                "Penerima": penerima, "HP_Penerima": hp_penerima, "Kota": kota, "Detail": detail,
                "Berat": berat, "Qty": qty, "Layanan": layanan, "Ongkir": ongkir, "Garansi": garansi, "Harga_Barang": harga_brg
            }
            st.session_state['page'] = 'Pembayaran'
            st.rerun()

# --- HALAMAN 4: PEMBAYARAN ---
def pembayaran_page():
    st.header("💰 Pembayaran")
    if st.session_state['show_resi']:
        components.html(st.session_state['html_resi_cache'], height=550)
        if st.button("Input Lagi"):
            st.session_state['show_resi'] = False
            st.session_state['page'] = 'Input'
            st.rerun()
        return

    d = st.session_state['form_data']
    total_sys = d['Ongkir'] + d['Garansi']
    
    c1, c2 = st.columns(2)
    with c1:
        st.info(f"Resi: {d['Resi']}")
        st.write(f"Layanan: {d['Layanan']}")
        st.write(f"Ongkir + Garansi: Rp {total_sys:,.0f}")
        metode = st.radio("Metode", ["Prepaid", "COD"])
        admin = total_sys * 0.05 if metode == "COD" else 0
        grand_total = total_sys + admin
        st.markdown(f"## Tagihan: Rp {grand_total:,.0f}")
    
    with c2:
        sub_metode = st.selectbox("Via", ["Cash", "Transfer"]) if metode == "Prepaid" else "Cash"
        if st.button("Proses & Cetak"):
            try:
                # Simpan ke Sheets
                row = [d['Resi'], str(datetime.now()), d['Pengirim'], d['HP_Pengirim'], d['Alamat_Pengirim'],
                       d['Penerima'], d['HP_Penerima'], "-", d['Kota'], "-", "-", "-", d['Detail'],
                       "Diproses", "-", "-", "-", "-", d['Berat'], d['Qty'], d['Layanan'], d['Harga_Barang'], d['Garansi'],
                       grand_total, metode, sub_metode, "LUNAS" if metode=="Prepaid" else "BELUM", "", "Pusat"]
                
                get_data("Data ( Active )").append_row(row)
                
                # Bikin Resi
                b64 = generate_barcode(d['Resi'])
                html = f"""
                <div style="border:2px solid #000;padding:15px;width:300px;font-family:sans-serif;margin:auto;">
                    <h2 style="text-align:center;margin:0;">LAJU LOGISTICS</h2>
                    <p style="text-align:center;">{d['Resi']}</p>
                    <div style="text-align:center;"><img src="data:image/png;base64,{b64}" width="80%"></div>
                    <hr>
                    <p><b>Pengirim:</b> {d['Pengirim']}<br><b>Penerima:</b> {d['Penerima']}<br>{d['Kota']}</p>
                    <hr>
                    <h3 style="text-align:right;">Rp {grand_total:,.0f}</h3>
                    <p style="text-align:center;">{metode} ({sub_metode})</p>
                    <button onclick="window.print()" style="background:#000;color:#fff;width:100%;padding:10px;cursor:pointer;">CETAK</button>
                </div>
                """
                st.session_state['html_resi_cache'] = html
                st.session_state['show_resi'] = True
                st.rerun()
            except Exception as e: st.error(str(e))

# --- HALAMAN 5: TRANSIT (OPTIMIZED MOBILE) ---
def transit_page():
    st.header("📲 Scan Mobile & Transit")
    
    st.warning("💡 Tips Kurir: Klik kolom di bawah, lalu tekan ikon 'Scan Text' [ 📷 ] di keyboard HP Anda untuk scan barcode otomatis!")
    
    resi = st.text_input("SCAN BARCODE DISINI (Klik)", placeholder="Aktifkan keyboard HP...")
    
    if resi:
        try:
            sheet = get_data("Data ( Active )")
            df = pd.DataFrame(sheet.get_all_records())
            df['No_Resi'] = df['No_Resi'].astype(str)
            
            cek = df[df['No_Resi'] == resi]
            if not cek.empty:
                idx = cek.index[0] + 2
                data = cek.iloc[0]
                
                st.success(f"📦 Paket Ditemukan: {data['Nama_Penerima']}")
                st.write(f"Tujuan: {data['Kota']}")
                
                c1, c2 = st.columns(2)
                cabang = st.session_state['user_info']['Cabang']
                
                with c1:
                    if st.button(f"📍 Sampai di {cabang}"):
                        sheet.update_cell(idx, 14, f"Transit di {cabang}")
                        sheet.update_cell(idx, 29, cabang)
                        st.success("Status Updated!")
                
                with c2:
                    st.write("📸 **Bukti Serah Terima**")
                    foto = st.camera_input("Foto Penerima")
                    if foto and st.button("✅ Selesai (Arsip)"):
                        # Logika Arsip
                        sheet.update_cell(idx, 14, "Diterima Customer")
                        sheet.update_cell(idx, 28, "https://foto-placeholder.com")
                        row = sheet.row_values(idx)
                        row.append(str(datetime.now()))
                        get_data("Arsip Data").append_row(row)
                        sheet.delete_rows(idx)
                        st.balloons()
                        st.success("Paket Selesai!")
            else:
                st.error("Resi tidak ditemukan!")
        except Exception as e: st.error(f"Error: {e}")

# --- HALAMAN 6: ADMIN (FIX KEUANGAN) ---
def admin_page():
    st.title("📊 Laporan Keuangan & Arsip")
    
    tab1, tab2 = st.tabs(["Laporan Keuangan", "Data Arsip"])
    
    with tab1:
        try:
            # Gabung Data
            df1 = pd.DataFrame(get_data("Data ( Active )").get_all_records())
            df2 = pd.DataFrame(get_data("Arsip Data").get_all_records())
            df = pd.concat([df1, df2], ignore_index=True)
            
            if not df.empty:
                # BERSIHKAN DATA RUPIAH AGAR BISA DIHITUNG
                df['Total_Bayar'] = df['Total_Ongkir'].apply(clean_currency)
                
                omzet = df['Total_Bayar'].sum()
                cash = df[df['Metode_Bayar'].str.contains("Cash", case=False, na=False)]['Total_Bayar'].sum()
                trf = df[df['Metode_Bayar'].str.contains("Transfer", case=False, na=False)]['Total_Bayar'].sum()
                
                k1, k2, k3 = st.columns(3)
                k1.metric("Total Omzet", f"Rp {omzet:,.0f}")
                k2.metric("Uang Cash (Kasir)", f"Rp {cash:,.0f}")
                k3.metric("Transfer Bank", f"Rp {trf:,.0f}")
                
                st.write("Rincian Transaksi:")
                st.dataframe(df[['No_Resi', 'Total_Ongkir', 'Tipe_Pembayaran', 'Metode_Bayar', 'Status']])
            else:
                st.info("Belum ada transaksi.")
        except Exception as e: st.error(f"Gagal hitung: {e}")
        
    with tab2:
        st.write("Data Paket Selesai (Arsip)")
        try:
            df_arsip = pd.DataFrame(get_data("Arsip Data").get_all_records())
            st.dataframe(df_arsip)
        except: st.write("Kosong")

# --- NAVIGASI ---
if st.session_state['logged_in']:
    pg = st.session_state['page']
    with st.sidebar:
        st.title("Menu")
        if st.button("🏠 Dashboard"): st.session_state['page'] = 'Dashboard'
        if st.button("📦 Input"): st.session_state['page'] = 'Input'
        if st.button("📲 Scan Transit"): st.session_state['page'] = 'Transit'
        if st.button("📊 Admin"): st.session_state['page'] = 'Admin'
        if st.button("Logout"): st.session_state['logged_in'] = False; st.rerun()
    
    if pg == 'Dashboard': dashboard_page()
    elif pg == 'Input': input_page()
    elif pg == 'Pembayaran': pembayaran_page()
    elif pg == 'Transit': transit_page()
    elif pg == 'Tracking': st.session_state['page'] = 'Dashboard'; st.info("Gunakan Dashboard") # Simplified
    elif pg == 'Admin': admin_page()
else:
    login_page()
