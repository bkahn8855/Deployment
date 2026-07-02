import streamlit as st
import streamlit.components.v1 as components 
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
# 1. 사용자 인증 정보
# ----------------------------------------------------
USER_CREDENTIALS = {
    "안병규": "911120", "김소영": "941225", "김기현": "840302", "김경현": "960308", 
    "문철호": "691113", "신선민": "900710", "김명선": "960611", "문현성": "910920", 
    "최솔잎": "950628", "류주영": "900426"
}

# --- 세션 상태 초기화 ---
if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False
if 'username' not in st.session_state:
    st.session_state['username'] = None
if 'login_time' not in st.session_state:
    st.session_state['login_time'] = None

# --- 파일 경로 설정 ---
data_file_path = "비용 정리_260702.xlsx" 
pdf_files_map = {
    "손익계산서_2022.pdf": "손익계산서_2022.pdf", "손익계산서_2023.pdf": "손익계산서_2023.pdf", 
    "손익계산서_2024.pdf": "손익계산서_2024.pdf", "재무상태표_2022.pdf": "재무상태표_2022.pdf", 
    "재무상태표_2023.pdf": "재무상태표_2023.pdf", "재무상태표_2024.pdf": "재무상태표_2024.pdf",
    "손익계산서_2025.pdf": "손익계산서_2025.pdf", "재무상태표_2025.pdf": "재무상태표_2025.pdf"
}

# ----------------------------------------------------
# 2. 헬퍼 함수 정의
# ----------------------------------------------------

# --- Google Sheets 설정 및 로깅 함수 (생략 없이 유지) ---
try:
    SHEET_ID = st.secrets["gcp_service_account"]["sheet_id"]
    SHEET_NAME = st.secrets["gcp_service_account"]["sheet_name"]
except Exception:
    SHEET_ID = None
    SHEET_NAME = None

@st.cache_data(ttl=300) 
def load_access_log_from_gsheets(sheet_id, sheet_name):
    if not SHEET_ID: return pd.DataFrame(columns=["login_time", "username", "status"])
    try:
        creds = st.secrets["gcp_service_account"]
        gc = gspread.service_account_from_dict(creds)
        sh = gc.open_by_key(sheet_id)
        worksheet = sh.worksheet(sheet_name)
        data_records = worksheet.get_all_records()
        df = pd.DataFrame(data_records)
        return df if not df.empty else pd.DataFrame(columns=["login_time", "username", "status"])
    except Exception: return pd.DataFrame(columns=["login_time", "username", "status"])

def write_access_log_to_gsheets(updated_data, sheet_id, sheet_name):
    if not SHEET_ID: return
    try:
        creds = st.secrets["gcp_service_account"]
        gc = gspread.service_account_from_dict(creds)
        sh = gc.open_by_key(sheet_id)
        worksheet = sh.worksheet(sheet_name)
        values_to_write = [updated_data.columns.values.tolist()] + updated_data.values.tolist()
        worksheet.update('A1', values_to_write, value_input_option='USER_ENTERED')
        load_access_log_from_gsheets.clear()
    except Exception: pass

def log_access(username, status):
    if not SHEET_ID: return
    try:
        data = load_access_log_from_gsheets(SHEET_ID, SHEET_NAME)
        new_log = pd.DataFrame([{
            "login_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "username": username,
            "status": status
        }])
        updated_data = pd.concat([new_log, data], ignore_index=True)
        write_access_log_to_gsheets(updated_data, SHEET_ID, SHEET_NAME)
    except Exception: pass

def logout():
    """로그아웃 처리 및 로그 기록."""
    if st.session_state["username"]:
        log_access(st.session_state["username"], "LOGOUT")
    st.session_state["authenticated"] = False
    st.session_state["username"] = None
    st.session_state["login_time"] = None
    st.experimental_rerun()

# --- 💡 수정된 PDF 표시 함수: st.components.v1.html 사용 ---
def display_pdf(file_path):
    """PDF 파일을 다운로드할 수 있는 버튼을 제공합니다 (Streamlit Cloud 호환)."""
    if not os.path.exists(file_path):
        st.warning(f"오류: **{file_path}** 파일을 찾을 수 없습니다. 파일 경로를 확인해주세요.")
        return

    try:
        with open(file_path, "rb") as f:
            pdf_bytes = f.read()
            base64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")

        file_name = os.path.basename(file_path)
        st.download_button(
            label=f"📥 {file_name} 다운로드",
            data=pdf_bytes,
            file_name=file_name,
            mime="application/pdf",
            use_container_width=True
        )

        st.info("브라우저 정책(특히 Chrome)으로 인해 PDF 미리보기가 차단될 수 있어, 대신 다운로드 방식으로 제공합니다.")

    except Exception as e:
        st.error(f"PDF를 로드하는 중 오류가 발생했습니다: {e}")

def color_negative_red(val):
    color = 'red' if isinstance(val, (int, float)) and val < 0 else 'black'
    return f'color: {color}'

@st.cache_data(ttl=3600) 
def load_data(file_path):
    # 데이터 로딩 로직은 그대로 유지
    if not os.path.exists(file_path):
        st.error(f"오류: 데이터 파일 '{file_path}'을 찾을 수 없습니다.")
        return pd.DataFrame() 
    try:
        df = pd.read_excel(file_path, sheet_name=0, engine="openpyxl")
    except Exception as e:
        st.error(f"오류: 엑셀 파일을 읽는 중 문제가 발생했습니다: {e}")
        return pd.DataFrame()

    df = df.dropna(subset=["연도", "월"]).copy()
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].astype(str).str.replace(',', '', regex=False).str.strip()
        df[col] = pd.to_numeric(df[col], errors='coerce')

    df["연월"] = pd.to_datetime(
        df["연도"].fillna(0).astype(int).astype(str) + 
        '-' + 
        df["월"].fillna(0).astype(int).astype(str).str.zfill(2), 
        format="%Y-%m"
    )
    df["연월_str"] = df["연월"].dt.strftime('%Y-%m')

    student_metrics = ["오전", "방과후", "초등", "오후"]
    if all(s in df.columns for s in student_metrics):
        df['총수강생'] = df[student_metrics].sum(axis=1)

    return df

# --- 로그인 폼 (인증되지 않은 경우에만 호출) ---
def login_form():
    """로그인 화면을 표시하고 사용자 인증을 처리합니다."""
    st.set_page_config(layout="centered", initial_sidebar_state="collapsed", page_title="로그인") 
    st.title("📊 재무 대시보드")
    st.subheader("로그인이 필요합니다.")
    st.markdown("---")
    
    col1, col2, col3 = st.columns([1, 2, 1]) 
    
    with col2: 
        with st.container(border=True):
            st.markdown("<h4 style='text-align: center;'>사용자 인증</h4>", unsafe_allow_html=True)
            
            with st.form("login_form", clear_on_submit=False):
                username = st.text_input("아이디 (이름)", placeholder="예: 홍길동")
                password = st.text_input("비밀번호 (생년월일 6자리)", type="password", placeholder="예: 900709")
                login_button = st.form_submit_button("로그인")

                if login_button:
                    if username in USER_CREDENTIALS and USER_CREDENTIALS[username] == password:
                        st.session_state['authenticated'] = True
                        st.session_state['username'] = username
                        st.session_state['login_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        
                        st.success(f"환영합니다, {username}님! 로그인에 성공했습니다. 대시보드를 로드합니다.")
                        log_access(username, "SUCCESS")
                        st.rerun() 
                    else:
                        st.error("로그인 정보가 올바르지 않습니다. 아이디와 비밀번호를 확인해주세요.")
                        log_access(username, "FAILED")

# --------------------------------------------------------------------------
# --- 메인 실행 흐름 (최상단 인증 체크) ---
# --------------------------------------------------------------------------

# 1. 인증되지 않았으면 로그인 폼을 표시합니다.
if not st.session_state['authenticated']:
    login_form()

# 2. 인증 성공 후 대시보드를 로드합니다.
else:
    st.set_page_config(layout="wide", page_title="재무 대시보드")
    st.title("📊 주식회사 비에이 재무 대시보드")
    
    # 캐시된 데이터 로드
    df_main = load_data(data_file_path)
    st.write([repr(c) for c in df_main.columns])
    
    if df_main is None or df_main.empty:
        st.error("대시보드 데이터를 로드하지 못했습니다. 파일과 내용을 확인해주세요. (인증 유지)")
        st.stop()
    
    # ---------------------
    # 3. Streamlit 레이아웃 (사이드바)
    # ---------------------
    st.sidebar.header("메뉴 선택")
    st.sidebar.markdown(f"---")
    st.sidebar.markdown(f"**현재 사용자**: **{st.session_state['username']}**")
    st.sidebar.markdown(f"**로그인 시각**: {st.session_state['login_time']}")
    st.sidebar.button("로그아웃", on_click=logout)

    menu = st.sidebar.radio("보고서 선택", ["재무상태표", "손익계산서", "수강생 흐름", "수입지출장부 흐름"], key="main_menu_radio")
    st.markdown("---")

    # ---------------------
    # 4. 메뉴별 동작
    # ---------------------

    if menu in ["재무상태표", "손익계산서"]:
        
        years = sorted(list(set(key.split('_')[1].split('.')[0] for key in pdf_files_map.keys() if menu in key)), reverse=True)
        
        if not years:
            st.error(f"오류: {menu}에 해당하는 PDF 파일 정보가 없습니다. 파일 이름을 확인해주세요.")
            st.stop()
        
        year = st.selectbox(
            f"{menu} 연도 선택", 
            years, 
            key=f"pdf_year_select_{menu}" 
        ) 
        
        pdf_file = pdf_files_map.get(f"{menu}_{year}.pdf")
        
        st.subheader(f"📄 {menu} ({year}년도)")
        
        if pdf_file:
            # 💡 수정된 함수 호출: components.html을 사용합니다.
            display_pdf(pdf_file)
        else:
            st.warning(f"경고: {menu}_{year}.pdf 파일 경로를 찾을 수 없습니다. GitHub에 업로드되었는지 확인하세요.")

    elif menu == "수강생 흐름":
        st.subheader("📈 월별 수강생 인원수 흐름")

        unique_months = sorted(df_main["연월_str"].unique())
        if not unique_months:
            st.error("데이터 파일에 유효한 월별 데이터가 없습니다.")
            st.stop()
            
        selected_range = st.select_slider(
            "기간 선택",
            options=unique_months,
            value=(unique_months[0], unique_months[-1]),
            key="student_range_slider"
        )
        start_date = selected_range[0]
        end_date = selected_range[1]

        df_filtered = df_main[(df_main["연월_str"] >= start_date) & (df_main["연월_str"] <= end_date)].copy()
        
        student_metrics = ["오전", "방과후", "초등", "오후"]
        available_students = [s for s in student_metrics if s in df_filtered.columns]
        
        if "총수강생" in df_filtered.columns:
            st.markdown("#### 수강생 인원수 추이")
            line_cols = available_students + ["총수강생"]
            
            df_line_plot = pd.melt(
                df_filtered,
                id_vars=["연월"],
                value_vars=[col for col in line_cols if col in df_filtered.columns], 
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

            st.markdown("#### 월별 수강생 구성 비율")
            fig_area = px.area(
                df_filtered,
                x="연월",
                y=[col for col in available_students if col in df_filtered.columns], 
                labels={"value": "인원수", "variable": "수강생 유형"},
                hover_data={"연월_str": True}
            )
            fig_area.update_xaxes(dtick="M1", tickformat="%Y-%m")
            fig_area.update_layout(hovermode="x unified")
            st.plotly_chart(fig_area, use_container_width=True)

            st.markdown("#### 수강생 인원수 데이터")
            df_table_cols = ["연도", "월"] + [col for col in line_cols if col in df_filtered.columns] 
            df_table_students = df_filtered[df_table_cols].copy()
            
            numeric_cols_to_int = [col for col in df_table_students.columns if col not in ["연도", "월"]]
            df_table_students[numeric_cols_to_int] = df_table_students[numeric_cols_to_int].astype(int, errors='ignore')
            
            st.dataframe(df_table_students.style.format(thousands=","), use_container_width=True)
        
        else:
            st.warning("수강생 관련 데이터(오전, 방과후, 초등, 오후)가 엑셀 파일에 없거나, 컬럼명이 일치하지 않습니다.")

    elif menu == "수입지출장부 흐름":
        st.subheader("💰 월별 + 누계 재무 흐름")
        
        unique_months = sorted(df_main["연월_str"].unique())
        if not unique_months:
            st.error("데이터 파일에 유효한 월별 데이터가 없습니다.")
            st.stop()
            
        selected_range = st.select_slider(
            "기간 선택",
            options=unique_months,
            value=(unique_months[0], unique_months[-1]),
            key="finance_range_slider"
        )

        start_date = selected_range[0]
        end_date = selected_range[1]

        df_filtered = df_main[(df_main["연월_str"] >= start_date) & (df_main["연월_str"] <= end_date)].copy()

        cumulative_cols = ["법인 안병규 입금", "법인 대출"]
        for col in cumulative_cols:
            if col in df_filtered.columns:
                df_filtered[f"{col} 누계"] = df_filtered[col].fillna(0).cumsum()

        all_metrics = ["법인 입금", "법인 출금", "법인 차액", "법인 잔액", "법인 매출", "법인 비용", "법인 영업이익", "법인 안병규 입금", "법인 안병규 입금 누계", "법인 대출", "법인 대출 누계"]
        st.write(df_filtered.columns.tolist())
        available_metrics = [m for m in all_metrics if m in df_filtered.columns]
        
        st.write("available_metrics =", available_metrics)
        selected_metrics = st.multiselect(
            "그래프에 표시할 지표 선택", 
            available_metrics, 
            default=["법인 매출", "법인 영업이익"],
            key="metric_multiselect"
        )
        
        final_cols_for_plot = []
        for m in selected_metrics:
            is_cumulative = False
            if m in cumulative_cols:
                cumulative_name = f"{m}누계"
                if cumulative_name in df_filtered.columns:
                    final_cols_for_plot.append(cumulative_name)
                    is_cumulative = True
            
            if m in df_filtered.columns:
                if not is_cumulative or m not in final_cols_for_plot:
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
