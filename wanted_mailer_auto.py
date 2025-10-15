import requests, smtplib, os, time
from datetime import datetime
from email.mime.text import MIMEText

# --- 하드코딩된 필터링 설정 ---
JOB_CATEGORY_ID = 518  # 경영/비즈니스 전체 (Wanted API 기준 ID)
MAX_EXPERIENCE_YEARS = 0 # 신입 (최소 경력 0년)
MAX_JOBS_TO_SEND = 5 # 메일에 포함할 최대 공고 수

LAST_ID_FILE = "last_id.txt"

# BASE_URL에 카테고리 필터를 적용하지 않고, fetch_all_jobs에서 동적으로 생성합니다.
MY_EMAIL = os.environ.get("MY_EMAIL")
MY_PASSWORD = os.environ.get("MY_PASSWORD")

# ===== 전체 페이지 순회 (특정 카테고리만) =====
def fetch_all_jobs(job_category_id, max_pages=5): # 최신 500개 내에서 필터링하도록 페이지 수를 줄였습니다.
    BASE_URL = f"https://www.wanted.co.kr/api/v4/jobs?country=kr&limit=100&job_sort=job.latest_order&job_category_ids={job_category_id}"

    all_jobs = []
    offset = 0
    while True:
        url = f"{BASE_URL}&offset={offset}"
        res = requests.get(url)
        if res.status_code != 200:
            print(f"⚠️ 요청 실패: {res.status_code}")
            break
        data = res.json()
        jobs = data.get("data", [])
        if not jobs:
            break
        all_jobs.extend(jobs)
        print(f"📦 {len(all_jobs)}개 로드 중...")
        
        # 100개 미만이 로드되거나, 지정된 최대 페이지(500개)를 넘으면 중단
        if len(jobs) < 100 or offset >= (max_pages - 1) * 100:
            break
        offset += 100
        time.sleep(0.5)
    print(f"✅ 총 {len(all_jobs)}개 공고 로드 완료 (카테고리 ID: {job_category_id})")
    return all_jobs

# ===== 필터링 (신입만) =====
def filter_jobs(jobs, max_years):
    filtered = []
    for j in jobs:
        # '신입' 조건: annual_from(최소 경력)이 0년과 같아야 함
        yrs = j.get("annual_from", 0)
        
        if yrs == max_years:
            filtered.append(j)
    return filtered

# ===== 마지막 발송 공고 추적 =====
def get_last_id():
    if not os.path.exists(LAST_ID_FILE):
        return None
    with open(LAST_ID_FILE, "r") as f:
        return f.read().strip()

def save_last_id(job_id):
    with open(LAST_ID_FILE, "w") as f:
        f.write(str(job_id))

# ===== 메일 빌드 =====
def build_email(jobs):
    html = f"<h2>📢 {datetime.now().strftime('%m월 %d일')} 새 채용공고 (최신 {len(jobs)}건)</h2><hr>"
    for j in jobs:
        html += f"""
        <div style='margin-bottom:15px; padding: 10px; border-bottom: 1px solid #eee;'>
            <b style='font-size: 1.1em;'>{j['company']['name']}</b> - {j['position']}<br>
            📍 {j['address'].get('full_location','')}<br>
            💰 리워드: {j['reward'].get('formatted_total', 'N/A')}<br>
            <a href='https://www.wanted.co.kr/wd/{j['id']}' target='_blank' style='color:#4A90E2; text-decoration: none;'>공고 바로 보기 &gt;</a>
        </div>
        """
    return html

# ===== 메일 전송 =====
def send_mail(to_email, content):
    msg = MIMEText(content, "html")
    msg["Subject"] = f"[원티드 알림] {datetime.now().strftime('%m월 %d일')} 경영/비즈니스 신입 공고 업데이트"
    msg["From"] = MY_EMAIL
    msg["To"] = to_email
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(MY_EMAIL, MY_PASSWORD)
        smtp.send_message(msg)
        print(f"✅ 메일 발송 완료 → {to_email}")

# ===== 실행 =====
if __name__ == "__main__":
    # MY_EMAIL을 메일 수신자로 사용
    TO_EMAIL = MY_EMAIL
    
    if not TO_EMAIL or not MY_PASSWORD:
        print("❌ 환경 변수 (MY_EMAIL 또는 MY_PASSWORD)가 설정되지 않았습니다. 스크립트를 종료합니다.")
        exit()
        
    print(f"🎯 조건: 직무=경영/비즈니스 전체 | 경력=신입 (0년)")

    # 1. API를 통해 '경영/비즈니스 전체' 최신 공고 로드 (최대 500개)
    all_jobs = fetch_all_jobs(JOB_CATEGORY_ID)
    
    # 2. 로드된 공고 중 '신입' 공고만 필터링
    jobs = filter_jobs(all_jobs, MAX_EXPERIENCE_YEARS)
    
    if not jobs:
        print("❌ 조건에 맞는 공고 없음")
        exit()

    last_id = get_last_id()
    latest_id = str(jobs[0]["id"])

    # 3. 새 공고 판단
    if last_id == latest_id:
        print("📭 새 공고 없음 — 메일 생략")
        exit()

    # 4. 새로운 공고만 추출
    new_jobs_full = []
    for job in jobs:
        if str(job["id"]) == last_id:
            break
        new_jobs_full.append(job)

    # 5. 메일 발송할 공고 수 (최대 5개) 제한
    new_jobs_to_send = new_jobs_full[:MAX_JOBS_TO_SEND]

    if new_jobs_to_send:
        print(f"✉️ 새 공고 {len(new_jobs_to_send)}건 발견. 메일 발송 시작...")
        html = build_email(new_jobs_to_send)
        send_mail(TO_EMAIL, html)
        save_last_id(latest_id)
    else:
        print("📭 새 공고 없음")
