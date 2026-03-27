/*
Google Apps Script Web App
1) 새 Apps Script 프로젝트 생성
2) 아래 코드 붙여넣기
3) SPREADSHEET_ID와 OPTIONAL_TOKEN 설정
4) 배포 > 새 배포 > 유형: 웹 앱
   - 실행 사용자: 본인
   - 액세스 권한: 링크가 있는 모든 사용자
5) 웹 앱 URL을 APPS_SCRIPT_WEB_APP_URL에 설정
*/

const SPREADSHEET_ID = "PUT_YOUR_SPREADSHEET_ID_HERE";
const OPTIONAL_TOKEN = ""; // 원하면 임의 문자열 설정

function doPost(e) {
  try {
    const payload = JSON.parse(e.postData.contents || "{}");
    if (OPTIONAL_TOKEN && payload.token !== OPTIONAL_TOKEN) {
      return jsonResponse({ ok: false, error: "invalid token" });
    }

    const sheetName = String(payload.sheet_name || "").trim();
    const headers = Array.isArray(payload.headers) ? payload.headers : [];
    const rows = Array.isArray(payload.rows) ? payload.rows : [];
    if (!sheetName || headers.length === 0 || rows.length === 0) {
      return jsonResponse({ ok: false, error: "sheet_name/headers/rows required" });
    }

    const ss = SpreadsheetApp.openById(SPREADSHEET_ID);
    let ws = ss.getSheetByName(sheetName);
    if (!ws) {
      ws = ss.insertSheet(sheetName);
    }

    const firstRow = ws.getLastRow() >= 1 ? ws.getRange(1, 1, 1, headers.length).getValues()[0] : [];
    const headerMissing = firstRow.join("") === "" || firstRow[0] !== headers[0];
    if (headerMissing) {
      ws.getRange(1, 1, 1, headers.length).setValues([headers]);
    }

    const startRow = ws.getLastRow() + 1;
    ws.getRange(startRow, 1, rows.length, headers.length).setValues(rows);

    return jsonResponse({ ok: true, inserted: rows.length, sheet: sheetName });
  } catch (err) {
    return jsonResponse({ ok: false, error: String(err) });
  }
}

function jsonResponse(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
