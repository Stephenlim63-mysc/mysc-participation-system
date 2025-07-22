import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import pandas as pd
from datetime import datetime
import pytz
import json
import os

# Firebase 설정 (보안 강화)
@st.cache_resource
def init_firebase():
    if not firebase_admin._apps:
        # 환경변수에서 Firebase 설정 읽기
        if os.getenv('FIREBASE_TYPE'):
            # 클라우드 배포용 (환경변수 사용)
            firebase_config = {
                "type": os.getenv('FIREBASE_TYPE'),
                "project_id": os.getenv('FIREBASE_PROJECT_ID'),
                "private_key_id": os.getenv('FIREBASE_PRIVATE_KEY_ID'),
                "private_key": os.getenv('FIREBASE_PRIVATE_KEY').replace('\\n', '\n').replace('\\"', '"').strip(),
                "client_email": os.getenv('FIREBASE_CLIENT_EMAIL'),
                "client_id": os.getenv('FIREBASE_CLIENT_ID'),
                "auth_uri": os.getenv('FIREBASE_AUTH_URI'),
                "token_uri": os.getenv('FIREBASE_TOKEN_URI'),
                "auth_provider_x509_cert_url": os.getenv('FIREBASE_AUTH_PROVIDER_CERT_URL'),
                "client_x509_cert_url": os.getenv('FIREBASE_CLIENT_CERT_URL')
            }
            cred = credentials.Certificate(firebase_config)
        else:
            # 로컬 개발용 (JSON 파일 사용)
            if os.path.exists("serviceAccountKey.json"):
                cred = credentials.Certificate("serviceAccountKey.json")
            else:
                st.error("Firebase 설정 파일을 찾을 수 없습니다.")
                st.stop()
        
        firebase_admin.initialize_app(cred)
    return firestore.client()

# 역할 매핑
ROLES = {
    "00": "사업개발",
    "05": "제안", 
    "10": "사업운영",
    "20": "컨설팅",
    "21": "오피스아워",
    "30": "집체교육",
    "31": "워크샵",
    "40": "정산"
}

# 페이지 설정
st.set_page_config(
    page_title="프로젝트 참여율 관리 시스템",
    page_icon="📊",
    layout="wide"
)

# CSS 스타일
st.markdown("""
<style>
    .main-header {
        background-color: #d4f0e8;
        padding: 10px 15px;
        border-radius: 8px;
        text-align: center;
        margin-bottom: 15px;
    }
    .main-header h1 {
        font-size: 24px;
        margin: 0;
        color: #333;
    }
    .step-container {
        background-color: #ffffff;
        padding: 20px;
        border: 1px solid #e0e0e0;
        border-radius: 5px;
        margin-bottom: 20px;
    }
    .error-message {
        color: #d9534f;
        font-weight: bold;
        background-color: #f8d7da;
        padding: 10px;
        border-radius: 4px;
        margin: 10px 0;
    }
    .success-message {
        color: #155724;
        font-weight: bold;
        background-color: #d4edda;
        padding: 10px;
        border-radius: 4px;
        margin: 10px 0;
    }
    .total-rate {
        font-size: 18px;
        font-weight: bold;
        text-align: right;
        margin-top: 20px;
    }
    .stButton > button {
        background-color: #007bff !important;
        color: white !important;
        border: none !important;
        border-radius: 5px !important;
        padding: 8px 16px !important;
        font-weight: 500 !important;
    }
    .stButton > button:hover {
        background-color: #0056b3 !important;
        color: white !important;
    }
    .stButton > button:focus {
        background-color: #0056b3 !important;
        color: white !important;
        box-shadow: none !important;
    }
</style>
""", unsafe_allow_html=True)

# 데이터 로딩 함수들
@st.cache_data
def load_employees():
    try:
        db = init_firebase()
        employees_ref = db.collection('employees')
        query = employees_ref.where('status', '==', 'ON')
        docs = query.stream()
        employees = []
        for doc in docs:
            data = doc.to_dict()
            data['id'] = doc.id
            employees.append(data)
        return employees
    except Exception as e:
        st.error(f"직원 데이터 로딩 실패: {str(e)}")
        return []

@st.cache_data
def load_projects():
    try:
        db = init_firebase()
        projects_ref = db.collection('projects')
        query = projects_ref.where('status', '==', 'ON')
        docs = query.stream()
        projects = []
        for doc in docs:
            data = doc.to_dict()
            data['id'] = doc.id
            projects.append(data)
        return projects
    except Exception as e:
        st.error(f"프로젝트 데이터 로딩 실패: {str(e)}")
        return []

def load_participations(employee_id, year, month):
    try:
        db = init_firebase()
        participations_ref = db.collection('participations')
        query = participations_ref.where('employeeId', '==', employee_id)\
                                 .where('year', '==', year)\
                                 .where('month', '==', month)
        docs = query.stream()
        participations = []
        for doc in docs:
            data = doc.to_dict()
            participations.append(data)
        return participations
    except Exception as e:
        st.error(f"참여 데이터 로딩 실패: {str(e)}")
        return []

def save_participations(employee_id, year, month, participations_data):
    try:
        db = init_firebase()
        
        # 한국 시간대 설정
        korea_tz = pytz.timezone('Asia/Seoul')
        current_time = datetime.now(korea_tz)
        
        # 기존 데이터 삭제
        old_query = db.collection('participations')\
                      .where('employeeId', '==', employee_id)\
                      .where('year', '==', year)\
                      .where('month', '==', month)
        old_docs = old_query.stream()
        
        batch = db.batch()
        for doc in old_docs:
            batch.delete(doc.reference)
        
        # 새 데이터 저장 (참여율이 0보다 큰 것만)
        for participation in participations_data:
            if participation['rate'] > 0:
                doc_id = f"{employee_id}_{participation['projectId']}_{participation['roleCode']}_{year}_{month}"
                doc_ref = db.collection('participations').document(doc_id)
                
                batch.set(doc_ref, {
                    'employeeId': employee_id,
                    'projectId': participation['projectId'],
                    'projectName': participation['projectName'],
                    'roleCode': participation['roleCode'],
                    'roleName': participation['roleName'],
                    'rate': participation['rate'],
                    'year': year,
                    'month': month,
                    'updatedAt': current_time
                })
        
        batch.commit()
        return True
    except Exception as e:
        st.error(f"저장 실패: {str(e)}")
        return False

# 메인 앱
def main():
    # 헤더
    st.markdown('<div class="main-header"><h1>MYSC 프로젝트 참여율 관리</h1></div>', unsafe_allow_html=True)
    
    # Firebase 초기화 테스트
    try:
        db = init_firebase()
        # Firebase 연결 성공 메시지 제거 (화면 정리)
    except Exception as e:
        st.error(f"Firebase 연결 실패: {str(e)}")
        st.error("Firebase 설정을 확인하세요.")
        st.stop()
    
    # 세션 상태 초기화
    if 'participations' not in st.session_state:
        st.session_state.participations = []
    if 'selected_employee' not in st.session_state:
        st.session_state.selected_employee = None
    if 'data_loaded' not in st.session_state:
        st.session_state.data_loaded = False
    
    # Step 1: 조회할 조건 선택
    st.markdown('<div class="step-container">', unsafe_allow_html=True)
    st.subheader("Step 1: 조회할 조건 선택")
    
    col1, col2, col3, col4 = st.columns([2, 2, 3, 3])
    
    with col1:
        current_year = datetime.now().year
        years = list(range(current_year + 1, current_year - 2, -1))
        selected_year = st.selectbox("년도", years, index=1)
    
    with col2:
        current_month = datetime.now().month
        months = list(range(1, 13))
        selected_month = st.selectbox("월", months, index=current_month-1)
    
    with col3:
        employees = load_employees()
        if employees:
            employee_options = ["-- 이름을 선택하세요 --"] + [emp['employeeId'] for emp in employees]
            selected_employee_name = st.selectbox("직원 선택", employee_options)
        else:
            st.error("직원 데이터를 불러올 수 없습니다.")
            st.stop()
    
    with col4:
        st.markdown("") # 약간의 공간
        load_button_disabled = (selected_employee_name == "-- 이름을 선택하세요 --")
        if st.button("조회 / 신규입력 시작", disabled=load_button_disabled, key="load_button"):
            # 선택된 직원 찾기
            selected_employee = next((emp for emp in employees if emp['employeeId'] == selected_employee_name), None)
            
            if selected_employee:
                st.session_state.selected_employee = selected_employee
                st.session_state.participations = []
                
                # 기존 데이터 로드
                existing_data = load_participations(selected_employee['employeeId'], selected_year, selected_month)
                projects = load_projects()
                project_dict = {p['projectId']: p for p in projects}
                
                for data in existing_data:
                    project = project_dict.get(data['projectId'])
                    if project:
                        st.session_state.participations.append({
                            'projectId': data['projectId'],
                            'projectName': project['projectName'],
                            'roleCode': data['roleCode'],
                            'roleName': ROLES.get(data['roleCode'], ''),
                            'rate': data['rate']
                        })
                
                st.session_state.data_loaded = True
                st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # 데이터가 로드된 경우만 나머지 화면 표시
    if st.session_state.data_loaded and st.session_state.selected_employee:
        # Step 2: 참여 항목 추가
        st.markdown('<div class="step-container">', unsafe_allow_html=True)
        st.subheader("Step 2: 참여 항목 추가")
        
        projects = load_projects()
        
        col1, col2, col3, col4 = st.columns([4, 2, 2, 2])
        
        with col1:
            project_options = ["-- 프로젝트 선택 --"] + [f"{p['projectName']} ({p['projectId']})" for p in projects]
            selected_project_display = st.selectbox("프로젝트 선택", project_options)
        
        with col2:
            role_options = ["-- 역할 선택 --"] + list(ROLES.values())
            selected_role_display = st.selectbox("역할 선택", role_options)
        
        with col3:
            participation_rate = st.number_input("참여율(%)", min_value=0, max_value=100, value=0)
        
        with col4:
            st.markdown("") # 공간 맞춤
            if st.button("목록에 추가", key="add_button"):
                if selected_project_display == "-- 프로젝트 선택 --" or selected_role_display == "-- 역할 선택 --":
                    st.error("프로젝트와 역할을 선택해주세요.")
                else:
                    # 프로젝트 ID 추출
                    project_id = selected_project_display.split('(')[-1].replace(')', '')
                    selected_project = next(p for p in projects if p['projectId'] == project_id)
                    
                    # 역할 코드 찾기
                    selected_role_code = next(k for k, v in ROLES.items() if v == selected_role_display)
                    
                    # 중복 체크
                    exists = any(p['projectId'] == project_id and p['roleCode'] == selected_role_code 
                               for p in st.session_state.participations)
                    
                    if exists:
                        st.error("이미 추가된 프로젝트-역할 조합입니다.")
                    else:
                        st.session_state.participations.append({
                            'projectId': project_id,
                            'projectName': selected_project['projectName'],
                            'roleCode': selected_role_code,
                            'roleName': selected_role_display,
                            'rate': participation_rate
                        })
                        st.rerun()
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Step 3: 참여 내역 표시 및 관리
        st.markdown('<div class="step-container">', unsafe_allow_html=True)
        st.subheader(f"{selected_year}년 {selected_month}월 참여 내역")
        st.write(f"**{st.session_state.selected_employee['employeeId']}**님의 참여 내역입니다.")
        
        if st.session_state.participations:
            # 참여 내역을 표 형태로 표시
            st.markdown("### 📋 참여 내역 목록")
            
            # 표 헤더 - 더 진하게
            st.markdown("""
            <div style="background-color: #007bff; color: white; padding: 12px; border-radius: 8px; margin-bottom: 5px;">
                <div style="display: flex;">
                    <div style="flex: 4; font-weight: bold; font-size: 16px;">📁 프로젝트명</div>
                    <div style="flex: 2; font-weight: bold; font-size: 16px; text-align: center;">👤 역할</div>
                    <div style="flex: 2; font-weight: bold; font-size: 16px; text-align: center;">📊 참여율(%)</div>
                    <div style="flex: 1; font-weight: bold; font-size: 16px; text-align: center;">⚙️ 관리</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # 각 참여 내역 행
            for i, p in enumerate(st.session_state.participations):
                # 배경색 설정 - 더 진하게
                if i % 2 == 0:
                    bg_color = "#e3f2fd"  # 연한 파란색
                    border_color = "#2196f3"
                else:
                    bg_color = "#f5f5f5"  # 연한 회색
                    border_color = "#9e9e9e"
                
                # 행 배경
                st.markdown(f"""
                <div style="background-color: {bg_color}; border-left: 4px solid {border_color}; padding: 15px; border-radius: 8px; margin: 8px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <div style="display: flex; align-items: center;">
                        <div style="flex: 4;">
                            <strong style="color: #1976d2; font-size: 15px;">📁 {p['projectName']}</strong>
                        </div>
                        <div style="flex: 2; text-align: center;">
                            <span style="background-color: #4caf50; color: white; padding: 6px 12px; border-radius: 20px; font-weight: bold; font-size: 13px;">
                                👤 {p['roleName']}
                            </span>
                        </div>
                        <div style="flex: 2; text-align: center;"></div>
                        <div style="flex: 1; text-align: center;"></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # 입력 필드와 버튼을 위한 컬럼
                col1, col2, col3, col4 = st.columns([4, 2, 2, 1])
                
                with col1:
                    st.write("")  # 공간
                
                with col2:
                    st.write("")  # 공간
                
                with col3:
                    new_rate = st.number_input(
                        f"참여율", 
                        min_value=0, 
                        max_value=100, 
                        value=p['rate'],
                        key=f"rate_{i}",
                        label_visibility="collapsed"
                    )
                    st.session_state.participations[i]['rate'] = new_rate
                
                with col4:
                    if st.button("🗑️ 삭제", key=f"delete_{i}", type="secondary"):
                        st.session_state.participations.pop(i)
                        st.rerun()
            
            # 총 합계 계산
            total_rate = sum(p['rate'] for p in st.session_state.participations)
            
            st.markdown(f'<div class="total-rate">총 합계: {total_rate}%</div>', unsafe_allow_html=True)
            
            # 에러 메시지
            if total_rate > 100:
                st.markdown('<div class="error-message">합계가 100%를 초과하였습니다.</div>', unsafe_allow_html=True)
            elif total_rate < 100:
                st.warning(f"합계가 {100-total_rate}% 부족합니다.")
            else:
                st.success("합계가 정확히 100%입니다!")
            
            # 저장 버튼
            save_disabled = len(st.session_state.participations) == 0
            if st.button("전체 저장하기", disabled=save_disabled):
                if total_rate != 100:
                    st.error("합계가 100%가 되어야 저장이 가능합니다.")
                else:
                    success = save_participations(
                        st.session_state.selected_employee['employeeId'],
                        selected_year,
                        selected_month,
                        st.session_state.participations
                    )
                    
                    if success:
                        st.success("성공적으로 저장되었습니다.")
                        st.session_state.data_loaded = False
                        st.session_state.participations = []
                        st.session_state.selected_employee = None
                        st.rerun()
        
        else:
            st.info("참여 내역이 없습니다. 위에서 항목을 추가해주세요.")
        
        st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
