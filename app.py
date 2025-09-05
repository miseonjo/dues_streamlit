import re
from pathlib import Path
import pandas as pd
import streamlit as st

st.set_page_config(page_title="학회비 납부 여부 조회", page_icon="💳", layout="centered")

BASE = Path(__file__).resolve().parent

# ✅ 데이터 후보 경로 (순서대로 검사해서 첫 번째로 존재하는 파일 사용)
LOCAL_XLSX = BASE.parent / "dues_app" / "Flask_py" / "학생이름_학번v2.xlsx"  # 로컬 개발용
TMP_XLSX = Path("/tmp/students.xlsx")  # 배포 후 행사 당일 업로드한 최신 파일
TMP_CSV  = Path("/tmp/students.csv")
CANDIDATES = [TMP_XLSX, TMP_CSV, LOCAL_XLSX]

def normalize_sid(s: str) -> str:
    s = str(s)
    s = re.sub(r"\.0$", "", s)
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"[^0-9]", "", s)
    return s.strip()

@st.cache_data(ttl=60)
def load_df():
    """엑셀/CSV 파일을 찾아 읽고, 컬럼/값을 정리해서 반환"""
    data_path = next((p for p in CANDIDATES if p.exists()), None)
    if data_path is None:
        return None, None

    try:
        if data_path.suffix.lower() in (".xlsx", ".xls"):
            df = pd.read_excel(data_path, engine="openpyxl", dtype={"학번": str})
        else:
            try:
                df = pd.read_csv(data_path, encoding="utf-8", dtype={"학번": str})
            except UnicodeDecodeError:
                df = pd.read_csv(data_path, encoding="cp949", dtype={"학번": str})
    except Exception as e:
        st.error(f"데이터 파일 읽기 오류: {e}")
        return None, None

    df.columns = [c.strip() for c in df.columns]
    if "학번" not in df.columns or "성명" not in df.columns:
        st.error("데이터 파일에 '학번' 또는 '성명' 열이 없습니다.")
        return None, data_path

    df["학번"] = df["학번"].astype(str).map(normalize_sid)
    df["성명"] = df["성명"].astype(str).str.strip()
    df = df.dropna(subset=["학번", "성명"]).reset_index(drop=True)
    return df[["성명", "학번"]], data_path

def get_admin_password():
    """secrets.toml이 없으면 None 반환(로컬에서 에러 방지)"""
    try:
        return st.secrets["ADMIN_PASSWORD"]
    except Exception:
        return None

def admin_panel():
    """관리자 업로드: 비번이 있는 배포 환경에서만 표시됨"""
    admin_pw = get_admin_password()
    if not admin_pw:
        # 로컬/개발 환경에서는 관리자 기능을 숨김 (단순 조회만)
        return

    st.subheader("🔑 관리자: 데이터 업로드(행사 당일 교체)")
    pw = st.text_input("관리자 비밀번호", type="password")
    uploaded = st.file_uploader("엑셀/CSV 업로드", type=["xlsx", "xls", "csv"])

    if uploaded and pw == admin_pw:
        target = TMP_XLSX if uploaded.name.lower().endswith(("xlsx", "xls")) else TMP_CSV
        target.write_bytes(uploaded.getbuffer())
        st.success(f"✅ 업로드 완료: {target}")
        st.cache_data.clear()  # 즉시 반영
    elif uploaded and pw != "":
        if pw != admin_pw:
            st.error("❌ 비밀번호가 올바르지 않습니다.")

def main():
    st.title("💳 학회비 납부 여부 조회")

    df, data_path = load_df()
    if df is None:
        st.warning("데이터 파일이 없습니다. (배포 시: 관리자 업로드, 로컬 시: dues_app/Flask_py/학생이름_학번v2.xlsx)")
        st.caption(f"로컬 기본 경로: `{LOCAL_XLSX}`")
        # 관리자 패널은 비번이 있어야만 표시됨
        with st.expander("관리자: 데이터 재업로드/교체", expanded=False):
            admin_panel()
        return

    st.caption(f"사용 중 데이터: `{data_path}`")

    sid = st.text_input("학번을 입력하세요", placeholder="예) 2023320033", max_chars=20)
    if st.button("검색") or sid:
        q = normalize_sid(sid)
        if not q:
            st.info("학번을 입력해 주세요.")
        else:
            row = df[df["학번"] == q]
            if not row.empty:
                name = row.iloc[0]["성명"]
                st.success(f"✅ {name} ({q}) 학생은 **납부자** 입니다.")
            else:
                st.error(f"❌ {q} 는 납부자 명단에 없습니다.")

    # (선택) 관리자 패널: 클라우드에서 비번 설정 시에만 보임
    with st.expander("관리자: 데이터 재업로드/교체", expanded=False):
        admin_panel()

if __name__ == "__main__":
    main()
