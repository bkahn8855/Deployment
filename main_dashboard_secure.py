import streamlit as st
import pandas as pd
import numpy as np
import io
import json
# 기존: from streamlit_gsheets import GSheetsConnection (제거됨)
import gspread # gspread 임포트
from gspread_dataframe import get_dataframe, set_with_dataframe # gspread-dataframe 임포트
from datetime import datetime

# --- 설정 및 초기화 ---
st.set_page_config(layout="wide")

# Streamlit Secrets에서 Google Sheets 설정 가져오기
try:
    # Google Sheets 연동에 필요한 시트 ID와 이름은 Secrets에서 직접 가져옵니다.
    # 연결 객체(st.connection) 대신 gspread 인증 정보를 직접 사용합니다.
    # secrets.toml의 [gsheets] 섹션에서 정보를 로드합니다.
    SHEET_ID = st.secrets["gsheets"]["sheet_id"]
    SHEET_NAME = st.secrets["gsheets"]["sheet_name"]
except Exception as e:
    st.error(f"Google Sheets Secrets 정보 로드 오류: Streamlit Secrets에 [gsheets] 섹션이 올바르게 설정되었는지 확인해주세요. 오류: {e}")
    st.stop()

# 인증 정보 (나중에 구글 시트로 관리)
USERS = {"test": "1234"} 

# 세션 상태 초기화
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "username" not in st.session_state:
    st.session_state["username"] = None

# --- 파일 경로 설정 ---
data_file_path = "비용 정리_250830.xlsx"

# PDF 파일 경로 
pdf_files = {
    "순익계산서_2022.pdf": "순익계산서_2022.pdf",
    "순익계산서_2023.pdf": "순익계산서_2023.pdf",
    "순익계산서_2024.pdf": "순익계산서_2024.pdf",
    "재무상태표_2022.pdf": "재무상태표_2022.pdf",
    "재무상태표_2023.pdf": "재무상태표_2023.pdf",
    "재무상태표_2024.pdf": "재무상태표_2024.pdf"
}

# --- Google Sheets 데이터 로드/쓰기 헬퍼 함수 ---

# @st.cache_data를 사용하여 Google Sheets 데이터를 캐시하는 함수
@st.cache_data(ttl=300) # 5분 동안 캐시
def load_access_log_from_gsheets(sheet_id, sheet_name):
    """gspread를 사용하여 Google Sheets에서 액세스 로그를 로드합니다."""
    try:
        # Streamlit Secrets에서 인증 정보 로드
        creds = st.secrets["gsheets"]
        
        # gspread 인증 및 연결
        gc = gspread.service_account_from_dict(creds)
        
        # 스프레드시트 및 워크시트 열기
        sh = gc.open_by_key(sheet_id)
        worksheet = sh.worksheet(sheet_name)
        
        # 워크시트 내용을 DataFrame으로 변환 (헤더는 첫 번째 행)
        # dtype=str로 설정하여 모든 데이터를 문자열로 가져옵니다.
        df = get_dataframe(worksheet, header=1, dtype=str)
        
        # DataFrame의 인덱스를 0부터 시작하도록 리셋 (옵션)
        df.index = range(len(df))
            
        return df
    except Exception as e:
        st.error(f"Google Sheets 연결 및 데이터 로드 오류: {e}")
        return pd.DataFrame() # 오류 시 빈 데이터프레임 반환

def write_access_log_to_gsheets(updated_data, sheet_id, sheet_name):
    """gspread를 사용하여 Google Sheets에 데이터프레임을 씁니다."""
    try:
        # Streamlit Secrets에서 인증 정보 로드
        creds = st.secrets["gsheets"]
        
        # gspread 인증 및 연결
        gc = gspread.service_account_from_dict(creds)
        
        # 스프레드시트 및 워크시트 열기
        sh = gc.open_by_key(sheet_id)
        worksheet = sh.worksheet(sheet_name)
        
        # DataFrame을 Google Sheets에 쓰기 (헤더 포함)
        # row=1, col=1은 A1 셀부터 쓰기 시작함을 의미합니다.
        set_with_dataframe(worksheet, updated_data, row=1, col=1, include_index=False, include_column_header=True)
        
        # 데이터 로드 캐시를 수동으로 지워 최신 데이터를 즉시 반영
        load_access_log_from_gsheets.clear()

    except Exception as e:
        # st.warning(f"접속 기록 로깅 실패: {e}") # 디버깅용
        pass

# --- Google Sheets 액세스 로그 기록 함수 ---
def log_access(username, status):
    try:
        # 현재 로그 데이터 로드
        data = load_access_log_from_gsheets(SHEET_ID, SHEET_NAME)
        
        new_log = pd.DataFrame([{
            "login_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "username": username,
            "status": status
        }])
        
        # 새 로그를 기존 데이터 위에 추가 (가장 최근 로그가 위로 오도록)
        updated_data = pd.concat([new_log, data], ignore_index=True)

        # Google Sheets에 다시 쓰기
        write_access_log_to_gsheets(updated_data, SHEET_ID, SHEET_NAME)

    except Exception as e:
        # st.warning(f"접속 기록 로깅 실패: {e}") # 디버깅용
        pass

# --- 인증 함수 ---
def authenticate():
    st.session_state["authenticated"] = True
    st.session_state["username"] = st.session_state.input_username
    log_access(st.session_state["username"], "SUCCESS")
    st.success("로그인 성공!")

def login_form():
    with st.sidebar:
        st.subheader("로그인")
        
        st.text_input("아이디 (예: test)", key="input_username")
        st.text_input("비밀번호 (예: 1234)", type="password", key="input_password")
        
        if st.button("로그인"):
            username = st.session_state.input_username
            password = st.session_state.input_password
            
            if username in USERS and USERS[username] == password:
                authenticate()
                st.experimental_rerun()
            else:
                log_access(username, "FAILED")
                st.error("아이디 또는 비밀번호가 잘못되었습니다.")

def logout():
    log_access(st.session_state["username"], "LOGOUT")
    st.session_state["authenticated"] = False
    st.session_state["username"] = None
    st.experimental_rerun()

# --- 데이터 로드 함수 (캐싱 적용) ---
@st.cache_data(ttl=3600) # 1시간 동안 캐시
def load_data(file_path):
    try:
        # pandas의 ExcelFile 객체를 사용하여 모든 시트 이름을 가져옴
        xls = pd.ExcelFile(file_path)
        sheet_names = xls.sheet_names
        
        data = {}
        for sheet_name in sheet_names:
            # 첫 번째 행을 헤더로 사용
            df = pd.read_excel(xls, sheet_name=sheet_name, header=0) 
            data[sheet_name] = df
            
        return data, sheet_names
    except FileNotFoundError:
        st.error(f"오류: 데이터 파일 '{file_path}'을 찾을 수 없습니다. GitHub에 파일이 업로드되었는지 확인해주세요.")
        return None, []
    except Exception as e:
        st.error(f"데이터 로드 중 오류가 발생했습니다: {e}")
        return None, []

# --- 대시보드 메인 페이지 ---
def main_dashboard(data, sheet_names):
    st.title("주식회사 비에이 재무 대시보드")
    
    st.markdown("---")
    
    # 사이드바에서 시트 선택
    selected_sheet = st.sidebar.selectbox("재무제표 시트 선택", sheet_names)
    
    if selected_sheet in data:
        df = data[selected_sheet]
        
        st.header(f"📊 {selected_sheet} 요약")
        
        # 데이터프레임 표시
        st.dataframe(df, use_container_width=True)
        
        st.markdown("---")
        
        # PDF 파일 다운로드 섹션
        st.header("📄 재무 보고서 (PDF 다운로드)")
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("순익계산서")
            for key, value in pdf_files.items():
                if "순익계산서" in key:
                    # 파일 경로가 맞는지 확인하고, 파일을 읽어서 다운로드 버튼에 연결
                    try:
                        with open(value, "rb") as file:
                            st.download_button(
                                label=f"⬇️ {key}",
                                data=file,
                                file_name=key,
                                mime="application/pdf"
                            )
                    except FileNotFoundError:
                        st.warning(f"경고: PDF 파일 '{key}'을 찾을 수 없습니다.")

        
        with col2:
            st.subheader("재무상태표")
            for key, value in pdf_files.items():
                if "재무상태표" in key:
                    # 파일 경로가 맞는지 확인하고, 파일을 읽어서 다운로드 버튼에 연결
                    try:
                        with open(value, "rb") as file:
                            st.download_button(
                                label=f"⬇️ {key}",
                                data=file,
                                file_name=key,
                                mime="application/pdf"
                            )
                    except FileNotFoundError:
                        st.warning(f"경고: PDF 파일 '{key}'을 찾을 수 없습니다.")

    else:
        st.error("선택한 시트의 데이터를 찾을 수 없습니다.")

# --- 메인 실행 흐름 ---
if st.session_state["authenticated"]:
    # 인증 성공 후 데이터 로드 및 대시보드 표시
    data, sheet_names = load_data(data_file_path)
    
    if data:
        # 로그아웃 버튼을 사이드바에 추가
        with st.sidebar:
            st.button("로그아웃", on_click=logout)
        main_dashboard(data, sheet_names)
    
else:
    # 로그인 폼 표시
    st.title("비에이 재무 대시보드")
    st.subheader("🔒 인증이 필요합니다.")
    st.markdown("---")
    login_form()