# AI 탐구 주제 · 세특 생성기

교사용 입력폼으로 학생별 탐구 주제/세특 문장을 생성하고, 결과를 Google Sheets에 누적 저장하는 Streamlit 앱입니다.

## 주요 기능
- 교사/학생 정보 입력
- 학생별 결과 누적 및 개별 다운로드(PDF 또는 Markdown)
- PDF/HWPX 본문 키워드 기반 추천
- 최근 7일 누적 로그 조회
- Google Apps Script Web App 저장
- OpenAI API 기반 세특 문장 고도화(선택)

## 실행
```powershell
cd "C:\Users\chris\Desktop\AI-탐구_세특\project_files_20260325"
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
streamlit run .\web_app.py
```

## Apps Script 연동
1. 구글 시트 생성
2. `확장 프로그램 > Apps Script` 열기
3. `scripts/google_apps_script_webapp.gs` 붙여넣기
4. `SPREADSHEET_ID`를 본인 시트 ID로 변경
5. `배포 > 새 배포 > 웹 앱`
6. 웹 앱 URL 복사 후 환경변수 설정

```powershell
$env:APPS_SCRIPT_WEB_APP_URL="https://script.google.com/macros/s/xxxxxxxx/exec"
$env:APPS_SCRIPT_TOKEN="optional"
```

## OpenAI 고도화(선택)
```powershell
$env:OPENAI_API_KEY="sk-..."
$env:OPENAI_MODEL="gpt-4o-mini"
```

앱에서 `OpenAI로 세특 문장 고도화` 체크 시 적용됩니다.  
키가 없거나 API 호출 실패 시 자동으로 로컬 문장 생성으로 fallback 됩니다.

## 주요 파일
- `web_app.py`
- `ai_setuk_generator.py`
- `integrations/google_sheets.py`
- `utils/openai_enhancer.py`
- `scripts/google_apps_script_webapp.gs`
