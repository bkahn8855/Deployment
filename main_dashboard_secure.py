import streamlit as st
import pandas as pd
import base64
import plotly.express as px
from datetime import datetime
import os # 파일 경로 확인을 위해 os 모듈 추가

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

# ----------------------------------------------------
# 2. 로그인 상태 관리 및 함수 정의
# ----------------------------------------------------

# 세션 상태 초기화
if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False
if 'username' not in st.session_state:
    st.session_state['username'] = None

def login_form():
    """로그인 화면을 표시하고 사용자 인증을 처리합니다."""
    # 로그인 화면용 페이지 설정 (대시보드와 다르게 중앙 정렬)
    st.set_page_config(layout="centered", initial_sidebar_state="collapsed")
    st.title("📊 재무 대시보드")
    st.subheader("로그인이 필요합니다.")
    st.markdown("---")
    
    # 중앙에 폼 배치
    with st.container(border=True):
        st.markdown("<h4 style='text-align: center;'>사용자 인증</h4>", unsafe_allow_html=True)
        with st.form("login_form", clear_on_submit=True):
            username = st.text_input("아이디 (이름)", placeholder="예: 홍길동")
            # 비밀번호는 생년월일 6자리 (YYYYMMDD 형식 대신 6자리 사용)
            password = st.text_input("비밀번호 (생년월일 6자리)", type="password", placeholder="예: 900709")
            login_button = st.form_submit_button("로그인")

            if login_button:
                # 딕셔너리에서 인증 정보 확인
                if username in USER_CREDENTIALS and USER_CREDENTIALS[username] == password:
                    st.session_state['authenticated'] = True
                    st.session_state['username'] = username
                    st.session_state['login_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    st.success(f"환영합니다, {username}님! 로그인에 성공했습니다.")
                    # Streamlit 앱을 새로고침하여 대시보드 화면으로 전환
                    st.rerun()
                else:
                    st.error("로그인 정보가 올바르지 않습니다. 아이디와 비밀번호를 확인해주세요.")

# PDF 표시 함수 (인증 후에도 사용)
def display_pdf(file):
    try:
        with open(file, "rb") as f:
            base64_pdf = base64.b64encode(f.read()).decode("utf-8")
        pdf_display = f'''
        <iframe src="data:application/pdf;base64,{base64_pdf}"
        width="100%" height="1000" type="application/pdf"></iframe>
        '''
        st.markdown(pdf_display, unsafe_allow_html=True)
    except FileNotFoundError:
        st.warning(f"오류: {file} 파일을 찾을 수 없습니다. 파일 경로를 확인해주세요.")

# 음수 값을 빨간색으로 표시하는 함수 (인증 후에도 사용)
def color_negative_red(val):
    color = 'red' if isinstance(val, (int, float)) and val < 0 else 'black'
    return f'color: {color}'

# ----------------------------------------------------
# 3. 로그인 확인 및 메인 대시보드 실행
# ----------------------------------------------------

if not st.session_state['authenticated']:
    login_form()
    # login_form 함수 내에서 st.stop()이 실행되므로, 이 이후 코드는 로그인 성공 시에만 실행됨

# ====================================================
# 메인 대시보드 시작 (로그인 성공 시에만 실행)
# ====================================================

st.set_page_config(layout="wide")
st.title("📊 주식회사 비에이 재무 대시보드")

# ---------------------
# 4. 데이터 로딩 및 클리닝 (기존 코드)
# ---------------------

# 주의: 깃허브 배포 시 로컬 경로는 사용할 수 없습니다.
# 배포 환경에 맞게 파일 경로를 조정하거나, Streamlit Secrets를 사용하여 파일을 업로드해야 합니다.
# 현재는 로컬 경로로 설정되어 있습니다.
file_path = "/Users/bkahn/Library/Mobile Documents/com~apple~CloudDocs/0. 사업/1. 결산/비용 정리_250830.xlsx"
st.caption(f"현재 데이터 파일 경로: {file_path}")

# 파일 존재 여부 확인 (로컬 개발 환경용)
if not os.path.exists(file_path):
    st.error(f"오류: 파일 '{file_path}'를 찾을 수 없습니다. 배포 시 Streamlit Secrets 또는 GitHub에 파일을 포함해야 합니다.")
    st.stop()

try:
    # 엑셀 파일 불러오기
    df = pd.read_excel(file_path, sheet_name=0, engine="openpyxl")
except Exception as e:
    st.error(f"오류: 엑셀 파일을 읽는 중 문제가 발생했습니다: {e}")
    st.stop()

# 결측 연도/월 제거
df = df.dropna(subset=["연도", "월"])

# 데이터 클리닝 및 타입 변환 (콤마 제거 후 숫자형으로)
for col in df.columns:
    if df[col].dtype == 'object':
        # 숫자형으로 변환하기 전에 문자열 데이터 정리
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

# 수강생 합계 및 누계 계산
if all(s in df.columns for s in student_metrics):
    df['총수강생'] = df[student_metrics].sum(axis=1)
    df['총수강생누계'] = df['총수강생'].cumsum()

# ---------------------
# 5. Streamlit 레이아웃 (기존 코드)
# ---------------------

st.sidebar.header("메뉴 선택")
# 사용자 정보 사이드바 하단에 표시
st.sidebar.markdown(f"---")
st.sidebar.markdown(f"**현재 사용자**: **{st.session_state['username']}**")
st.sidebar.markdown(f"**로그인 시각**: {st.session_state['login_time']}")

menu = st.sidebar.radio("보고서 선택", ["재무상태표", "손익계산서", "수강생 흐름", "수입지출장부 흐름"])

# ---------------------
# 6. 메뉴별 동작 (기존 코드)
# ---------------------
if menu in ["재무상태표", "손익계산서"]:
    # PDF 파일도 배포 환경에서는 경로를 조정해야 합니다.
    years = [2022, 2023, 2024]
    year = st.selectbox("연도 선택", years)
    pdf_file = f"{menu}_{year}.pdf"
    st.subheader(f"{menu} ({year}년도)")
    display_pdf(pdf_file)

elif menu == "수강생 흐름":
    st.subheader("월별 수강생 인원수 흐름")

    unique_months = sorted(df["연월_str"].unique())
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
        # 1. 누계 포함 선 그래프
        st.subheader("수강생 인원수 추이")
        
        line_cols = available_students + ["총수강생"]
        df_line_plot = pd.melt(
            df_filtered,
            id_vars=["연월"],
            value_vars=line_cols,
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
        st.subheader("월별 수강생 구성 비율")
        fig_area = px.area(
            df_filtered,
            x="연월",
            y=available_students,
            labels={"value": "인원수", "variable": "수강생 유형"},
            hover_data={"연월_str": True}
        )
        fig_area.update_xaxes(dtick="M1", tickformat="%Y-%m")
        fig_area.update_layout(hovermode="x unified")
        st.plotly_chart(fig_area, use_container_width=True)

        # 3. 데이터 표
        st.subheader("수강생 인원수 데이터")
        df_table_students = df_filtered[["연도", "월"] + line_cols].copy()
        
        # Ensure that numeric columns are integers before formatting
        numeric_cols_to_int = [col for col in df_table_students.columns if col not in ["연도", "월"]]
        df_table_students[numeric_cols_to_int] = df_table_students[numeric_cols_to_int].astype(int)
        
        st.dataframe(df_table_students.style.format(thousands=","), use_container_width=True)
    
    else:
        st.warning("수강생 관련 데이터(오전, 방과후, 초등, 오후)가 엑셀 파일에 없거나, 컬럼명이 일치하지 않습니다.")

elif menu == "수입지출장부 흐름":
    st.subheader("월별 + 누계 재무 흐름")

    unique_months = sorted(df["연월_str"].unique())
    selected_range = st.select_slider(
        "기간 선택",
        options=unique_months,
        value=(unique_months[0], unique_months[-1])
    )

    start_date = selected_range[0]
    end_date = selected_range[1]

    df_filtered = df[(df["연월_str"] >= start_date) & (df["연월_str"] <= end_date)].copy()

    cumulative_cols = ["총안병규입금", "총대출"]
    for col in cumulative_cols:
        if col in df_filtered.columns:
            df_filtered[f"{col}누계"] = df_filtered[col].fillna(0).cumsum()
        else:
            df_filtered[f"{col}누계"] = 0

    all_metrics = ["총입금", "총출금", "총차액", "총잔액", "총매출", "영업매출", "기타매출", "총비용", "고정비용", "변동비용", "총영업이익", "총안병규입금", "총대출"]
    available_metrics = [m for m in all_metrics if m in df.columns]
    
    selected_metrics = st.multiselect(
        "그래프에 표시할 지표 선택", 
        available_metrics, 
        default=available_metrics
    )
    
    final_cols_for_plot = []
    for m in selected_metrics:
        if m in cumulative_cols and f"{m}누계" in df_filtered.columns:
            final_cols_for_plot.append(f"{m}누계")
        elif m in df_filtered.columns:
            final_cols_for_plot.append(m)

    if final_cols_for_plot:
        try:
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

            st.subheader("그래프에 사용된 데이터 표")
            df_table_cols = ["연도", "월"] + final_cols_for_plot
            df_table = df_filtered[df_table_cols].copy()
            
            styled_df = df_table.style.applymap(color_negative_red).format(thousands=",")
            st.dataframe(styled_df, use_container_width=True)

        except Exception as e:
            st.error(f"그래프를 그리는 중 오류가 발생했습니다: {e}")
            st.warning("데이터프레임의 컬럼명과 선택 지표가 일치하는지 확인해주세요.")
            # st.dataframe(df_filtered) # 디버깅용으로 주석 처리

    else:
        st.warning("선택한 지표의 데이터가 없거나, 엑셀 파일의 컬럼명이 일치하지 않습니다.")
