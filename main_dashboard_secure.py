import streamlit as st
import streamlit.components.v1 as components # components 모듈 임포트
import pandas as pd
import numpy as np
import io
import json
import gspread 
import plotly.express as px
import base64
from datetime import datetime
import os
import time

# ----------------------------------------------------
# 1. 사용자 인증 정보 (ID: 이름, PW: 생년월일 6자리)
# ----------------------------------------------------
USER_CREDENTIALS = {
    "안병규": "911120",
    "김소영": "941225",
    "김기현": "840302",
    "김경현": "960308",
    "문철호": "691113",
    "신선민": "900710",
    "김명선": "960611",
    "문현성": "910920",
    "최솔잎": "950628"
}

# --- Google Sheets 설정 및 초기화 ---

# Streamlit Secrets에서 Google Sheets 설정 가져오기
try:
    # [gcp_service_account] 섹션에서 정보를 로드합니다.
    SHEET_ID = st.secrets["gcp_service_account"]["sheet_id"]
    SHEET_NAME = st.secrets["gcp_service_account"]["sheet_name"]
except Exception as e:
    # Google Sheets Secrets 정보 로드 오류 발생 시 사용자에게 알림
    st.error(f"Google Sheets Secrets 정보 로드 오류: Streamlit Secrets에 [gcp_service_account] 섹션이 올바르게 설정되었는지 확인해주세요. 오류: {e}")
    st.stop()


# --- 세션 상태 초기화 ---
if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False
if 'username' not in st.session_state:
    st.session_state['username'] = None
if 'login_time' not in st.session_state:
    st.session_state['login_time'] = None


# --- 파일 경로 설정 (GitHub/Streamlit 배포 환경 기준) ---
data_file_path = "비용 정리_250830.xlsx"

# PDF 파일 경로 (앱 루트 경로 기준)
pdf_files_map = {
    "손익계산서_2022.pdf": "손익계산서_2022.pdf",
    "손익계산서_2023.pdf": "손익계산서_2023.pdf",
    "손익계산서_2024.pdf": "손익계산서_2024.pdf",
    "재무상태표_2022.pdf": "재무상태표_2022.pdf",
    "재무상태표_2023.pdf": "재무상태표_2023.pdf",
    "재무상태표_2024.pdf": "재무상태표_2024.pdf"
}

# --- Google Sheets 데이터 로드/쓰기 헬퍼 함수 (기존 로직 유지) ---

@st.cache_data(ttl=300) # 5분 동안 캐시
def load_access_log_from_gsheets(sheet_id, sheet_name):
    """gspread의 기본 기능을 사용하여 Google Sheets에서 액세스 로그를 로드합니다."""
    try:
        creds = st.secrets["gcp_service_account"]
        gc = gspread.service_account_from_dict(creds)
        sh = gc.open_by_key(sheet_id)
        worksheet = sh.worksheet(sheet_name)
        data_records = worksheet.get_all_records()
        df = pd.DataFrame(data_records)
        
        if df.empty:
             return pd.DataFrame(columns=["login_time", "username", "status"])

        return df
    except Exception as e:
        # st.error(f"Google Sheets 연결 및 데이터 로드 오류: {e}") # 사용자에게 보이지 않게 처리
        return pd.DataFrame(columns=["login_time", "username", "status"])

def write_access_log_to_gsheets(updated_data, sheet_id, sheet_name):
    """gspread의 기본 기능을 사용하여 Google Sheets에 데이터프레임을 씁니다."""
    try:
        creds = st.secrets["gcp_service_account"]
        gc = gspread.service_account_from_dict(creds)
        sh = gc.open_by_key(sheet_id)
        worksheet = sh.worksheet(sheet_name)
        
        # DataFrame을 리스트 오브 리스트(LoL) 형태로 변환 (헤더 포함)
        values_to_write = [updated_data.columns.values.tolist()] + updated_data.values.tolist()
        
        # Google Sheets에 데이터 쓰기 (A1부터 시작)
        worksheet.update('A1', values_to_write)
        
        # 데이터 로드 캐시를 수동으로 지워 최신 데이터를 즉시 반영
        load_access_log_from_gsheets.clear()

    except Exception as e:
        # st.warning(f"접속 기록 로깅 실패: {e}") # 디버깅용
        pass

# --- Google Sheets 액세스 로그 기록 함수 ---
def log_access(username, status):
    try:
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

# --- 대시보드 헬퍼 함수 (요청된 코드에서 가져옴) ---

# PDF 표시 함수 (iframe HTML 문자열 반환)
@st.cache_data
def display_pdf(file):
    try:
        # 파일 존재 여부 확인
        if not os.path.exists(file):
            return f"오류: {file} 파일을 찾을 수 없습니다. GitHub에 업로드되었는지 확인해주세요."

        with open(file, "rb") as f:
            base64_pdf = base64.b64encode(f.read()).decode("utf-8")
        
        # Base64 데이터를 포함한 iframe HTML 문자열 생성
        pdf_display = f'''
        <iframe src="data:application/pdf;base64,{base64_pdf}"
        width="100%" height="1000" type="application/pdf"></iframe>
        '''
        return pdf_display
    except Exception as e:
        return f"오류: PDF 파일을 표시하는 중 문제가 발생했습니다: {e}"

# 음수 값을 빨간색으로 표시하는 함수
def color_negative_red(val):
    color = 'red' if isinstance(val, (int, float)) and val < 0 else 'black'
    return f'color: {color}'

# --- 데이터 로드 및 클리닝 함수 ---
@st.cache_data(ttl=3600) # 1시간 동안 캐시
def load_data(file_path):
    # 파일 존재 여부 확인 (배포 환경)
    if not os.path.exists(file_path):
        st.error(f"오류: 데이터 파일 '{file_path}'을 찾을 수 없습니다. GitHub에 파일을 포함해야 합니다.")
        st.stop()
        
    try:
        # 엑셀 파일 불러오기
        df = pd.read_excel(file_path, sheet_name=0, engine="openpyxl")
    except Exception as e:
        st.error(f"오류: 엑셀 파일을 읽는 중 문제가 발생했습니다: {e}")
        st.stop()

    # 결측 연도/월 제거
    df = df.dropna(subset=["연도", "월"]).copy()

    # 데이터 클리닝 및 타입 변환 (콤마 제거 후 숫자형으로)
    for col in df.columns:
        # 문자열을 처리하여 숫자형으로 변환
        if df[col].dtype == 'object':
            df[col] = df[col].astype(str).str.replace(',', '', regex=False).str.strip()
        # 숫자형 변환 (변환 불가 시 NaN으로 처리)
        df[col] = pd.to_numeric(df[col], errors='coerce')

    # 연월 열 생성 (Plotly용)
    df["연월"] = pd.to_datetime(df["연도"].astype(int).astype(str) + '-' + df["월"].astype(int).astype(str).str.zfill(2), format="%Y-%m")
    df["연월_str"] = df["연월"].dt.strftime('%Y-%m')

    # 수강생 관련 컬럼을 정수형으로 변환
    student_metrics = ["오전", "방과후", "초등", "오후"]
    for col in student_metrics:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)

    # 수강생 합계 계산 (누계는 제외)
    if all(s in df.columns for s in student_metrics):
        df['총수강생'] = df[student_metrics].sum(axis=1)
        # df['총수강생누계'] = df['총수강생'].cumsum() # 누계 계산 로직 제거

    return df

# --- 로그인 폼 및 인증 로직 ---

def login_form():
    """로그인 화면을 표시하고 사용자 인증을 처리합니다."""
    # 로그인 화면용 페이지 설정 (대시보드와 다르게 중앙 정렬)
    st.set_page_config(layout="centered", initial_sidebar_state="collapsed")
    st.title("📊 재무 대시보드")
    st.subheader("로그인이 필요합니다.")
    st.markdown("---")
    
    login_placeholder = st.empty() # 로그인 메시지를 표시할 공간

    # 중앙에 폼 배치
    with login_placeholder.container(border=True):
        st.markdown("<h4 style='text-align: center;'>사용자 인증</h4>", unsafe_allow_html=True)
        with st.form("login_form", clear_on_submit=True):
            username = st.text_input("아이디 (이름)", placeholder="예: 홍길동")
            password = st.text_input("비밀번호 (생년월일 6자리)", type="password", placeholder="예: 900709")
            login_button = st.form_submit_button("로그인")

            if login_button:
                # 딕셔너리에서 인증 정보 확인
                if username in USER_CREDENTIALS and USER_CREDENTIALS[username] == password:
                    st.session_state['authenticated'] = True
                    st.session_state['username'] = username
                    st.session_state['login_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    # 성공 메시지 표시 후 로그 기록
                    st.success(f"환영합니다, {username}님! 로그인에 성공했습니다. 잠시 후 대시보드로 이동합니다.")
                    log_access(username, "SUCCESS")
                    time.sleep(1) # 잠시 대기
                    # Streamlit 앱을 새로고침하여 대시보드 화면으로 전환
                    st.rerun()
                else:
                    # 실패 메시지 표시 후 로그 기록
                    st.error("로그인 정보가 올바르지 않습니다. 아이디와 비밀번호를 확인해주세요.")
                    log_access(username, "FAILED")
                    # 실패 시 st.rerun() 대신 다시 폼을 보여줌 (clear_on_submit=True에 의해 입력값은 초기화됨)

def logout():
    """로그아웃 처리 및 로그 기록."""
    if st.session_state["username"]:
        log_access(st.session_state["username"], "LOGOUT")
    st.session_state["authenticated"] = False
    st.session_state["username"] = None
    st.session_state["login_time"] = None
    st.experimental_rerun()


# --- 대시보드 메인 페이지 (요청된 코드 통합) ---
def main_dashboard(df):
    st.set_page_config(layout="wide")
    st.title("📊 주식회사 비에이 재무 대시보드")
    
    # ---------------------
    # 5. Streamlit 레이아웃
    # ---------------------

    st.sidebar.header("메뉴 선택")
    # 사용자 정보 사이드바 하단에 표시
    st.sidebar.markdown(f"---")
    st.sidebar.markdown(f"**현재 사용자**: **{st.session_state['username']}**")
    st.sidebar.markdown(f"**로그인 시각**: {st.session_state['login_time']}")
    
    # 로그아웃 버튼
    st.sidebar.button("로그아웃", on_click=logout)

    menu = st.sidebar.radio("보고서 선택", ["재무상태표", "손익계산서", "수강생 흐름", "수입지출장부 흐름"])
    
    st.markdown("---")

    # ---------------------
    # 6. 메뉴별 동작
    # ---------------------
    if menu in ["재무상태표", "손익계산서"]:
        
        # PDF 파일도 배포 환경에서는 경로를 조정해야 합니다.
        years = sorted(list(set(key.split('_')[1].split('.')[0] for key in pdf_files_map.keys() if menu in key)), reverse=True)
        
        if not years:
            st.error(f"오류: {menu}에 해당하는 PDF 파일 정보가 없습니다.")
            return

        year = st.selectbox("연도 선택", years)
        
        # 파일 이름 찾기
        pdf_file_key = f"{menu}_{year}.pdf"
        pdf_file = pdf_files_map.get(pdf_file_key)
        
        st.subheader(f"📄 {menu} ({year}년도)")
        
        if pdf_file:
            pdf_content = display_pdf(pdf_file)
            
            # components.html을 사용하여 브라우저 보안 문제를 우회 시도
            if pdf_content.startswith("<iframe"):
                components.html(pdf_content, height=1000, scrolling=True)
            else:
                # 에러 메시지인 경우 (파일 없음 등)
                st.error(pdf_content)
        else:
            st.warning(f"경고: {pdf_file_key}에 해당하는 PDF 파일을 찾을 수 없습니다. GitHub에 업로드되었는지 확인하세요.")

    elif menu == "수강생 흐름":
        st.subheader("📈 월별 수강생 인원수 흐름")

        unique_months = sorted(df["연월_str"].unique())
        if not unique_months:
            st.error("데이터 파일에 유효한 월별 데이터가 없습니다.")
            return

        # 기본 슬라이더 값 설정 (가장 오래된 월과 가장 최근 월)
        selected_range = st.select_slider(
            "기간 선택",
            options=unique_months,
            value=(unique_months[0], unique_months[-1])
        )
        start_date = selected_range[0]
        end_date = selected_range[1]

        df_filtered = df[(df["연월_str"] >= start_date) & (df["연월_str"] <= end_date)].copy()
        
        student_metrics = ["오전", "방과후", "초등", "오후"]
        available_students = [s for s in student_metrics if s in df_filtered.columns]
        
        if "총수강생" in df_filtered.columns:
            # 1. 월별 선 그래프
            st.markdown("#### 수강생 인원수 추이")
            
            # '총수강생'만 포함 (누계 제외)
            line_cols = available_students + ["총수강생"]
            
            df_line_plot = pd.melt(
                df_filtered,
                id_vars=["연월"],
                value_vars=[col for col in line_cols if col in df_filtered.columns], # 존재하는 컬럼만 선택
                var_name="수강생 유형",
                value_name="인원수"
            )
            df_line_plot = df_line_plot.dropna(subset=["인원수"]).reset_index(drop=True)
            
            fig_line = px.line(
                df_line_plot,
                x="연월",
                y="인원수",
                color="수강생 유형",
                markers=True,
                hover_data={"연월": "|%Y-%m", "수강생 유형": True, "인원수": ":,.0f"}
            )
            fig_line.update_xaxes(dtick="M1", tickformat="%Y-%m")
            fig_line.update_layout(hovermode="x unified")
            st.plotly_chart(fig_line, use_container_width=True)

            # 2. 누적 면적 그래프 (구성 비율)
            st.markdown("#### 월별 수강생 구성 비율")
            fig_area = px.area(
                df_filtered,
                x="연월",
                y=[col for col in available_students if col in df_filtered.columns], # 존재하는 컬럼만 선택
                labels={"value": "인원수", "variable": "수강생 유형"},
                hover_data={"연월_str": True}
            )
            fig_area.update_xaxes(dtick="M1", tickformat="%Y-%m")
            fig_area.update_layout(hovermode="x unified")
            st.plotly_chart(fig_area, use_container_width=True)

            # 3. 데이터 표
            st.markdown("#### 수강생 인원수 데이터")
            # '총수강생누계' 제외
            df_table_cols = ["연도", "월"] + [col for col in line_cols if col in df_filtered.columns] 
            df_table_students = df_filtered[df_table_cols].copy()
            
            # Ensure that numeric columns are integers before formatting
            numeric_cols_to_int = [col for col in df_table_students.columns if col not in ["연도", "월"]]
            df_table_students[numeric_cols_to_int] = df_table_students[numeric_cols_to_int].astype(int, errors='ignore')
            
            st.dataframe(df_table_students.style.format(thousands=","), use_container_width=True)
        
        else:
            st.warning("수강생 관련 데이터(오전, 방과후, 초등, 오후)가 엑셀 파일에 없거나, 컬럼명이 일치하지 않습니다.")

    elif menu == "수입지출장부 흐름":
        st.subheader("💰 월별 + 누계 재무 흐름")

        unique_months = sorted(df["연월_str"].unique())
        if not unique_months:
            st.error("데이터 파일에 유효한 월별 데이터가 없습니다.")
            return
            
        selected_range = st.select_slider(
            "기간 선택",
            options=unique_months,
            value=(unique_months[0], unique_months[-1])
        )

        start_date = selected_range[0]
        end_date = selected_range[1]

        df_filtered = df[(df["연월_str"] >= start_date) & (df["연월_str"] <= end_date)].copy()

        # 누계 계산 (요청된 로직 유지)
        cumulative_cols = ["총안병규입금", "총대출"]
        for col in cumulative_cols:
            if col in df_filtered.columns:
                df_filtered[f"{col}누계"] = df_filtered[col].fillna(0).cumsum()
            # 누계 컬럼이 없을 경우, df_filtered에 추가하지 않아 에러를 방지

        all_metrics = ["총입금", "총출금", "총차액", "총잔액", "총매출", "영업매출", "기타매출", "총비용", "고정비용", "변동비용", "총영업이익", "총안병규입금", "총대출"]
        available_metrics = [m for m in all_metrics if m in df.columns]
        
        selected_metrics = st.multiselect(
            "그래프에 표시할 지표 선택", 
            available_metrics, 
            default=["총잔액", "총영업이익"] # 기본값 설정
        )
        
        final_cols_for_plot = []
        for m in selected_metrics:
            is_cumulative = False
            # 누계 컬럼 확인 및 추가
            if m in cumulative_cols:
                cumulative_name = f"{m}누계"
                if cumulative_name in df_filtered.columns:
                    final_cols_for_plot.append(cumulative_name)
                    is_cumulative = True
            
            # 원래 컬럼 추가 (누계가 아닌 경우 또는 누계 외에 월별 값도 보고 싶은 경우)
            if not is_cumulative and m in df_filtered.columns:
                final_cols_for_plot.append(m)


        if final_cols_for_plot:
            try:
                st.markdown("#### 선택 지표 추이 그래프")
                df_plot = pd.melt(
                    df_filtered,
                    id_vars=["연월"],
                    value_vars=final_cols_for_plot,
                    var_name="지표",
                    value_name="값"
                )
                df_plot = df_plot.dropna(subset=["값"]).reset_index(drop=True)
                
                fig = px.line(
                    df_plot,
                    x="연월",
                    y="값",
                    color="지표",
                    markers=True,
                    hover_data={"연월": "|%Y-%m", "지표": True, "값": ":,.0f"}
                )
                
                fig.update_xaxes(dtick="M1", tickformat="%Y-%m")
                fig.update_layout(hovermode="x unified")
                st.plotly_chart(fig, use_container_width=True)

                st.markdown("#### 그래프에 사용된 데이터 표")
                df_table_cols = ["연도", "월"] + final_cols_for_plot
                df_table = df_filtered[df_table_cols].copy()
                
                styled_df = df_table.style.applymap(color_negative_red).format(thousands=",")
                st.dataframe(styled_df, use_container_width=True)

            except Exception as e:
                st.error(f"그래프를 그리는 중 오류가 발생했습니다: {e}")
                st.warning("데이터프레임의 컬럼명과 선택 지표가 일치하는지 확인해주세요.")

        else:
            st.warning("선택한 지표의 데이터가 없거나, 엑셀 파일의 컬럼명이 일치하지 않습니다.")


# --- 메인 실행 흐름 ---

if st.session_state["authenticated"]:
    # 인증 성공 후 데이터 로드 및 대시보드 표시
    df_main = load_data(data_file_path) 
    
    if df_main is not None and not df_main.empty:
        main_dashboard(df_main)
    else:
        # 데이터 로드 실패 시 에러는 load_data 내부에서 이미 표시됨
        st.error("대시보드 데이터를 로드하지 못했습니다. 파일과 내용을 확인해주세요.")
    
else:
    # 로그인 폼 표시
    login_form()
