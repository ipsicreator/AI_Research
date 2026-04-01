# 통합 메인 화면 Figma 시안 가이드 (3구역)

## 1) 화면 목적
- 첫 화면에서 3개 서비스로 즉시 이동
- 서비스 간 상호 이동(1↔2)과 3번 신청 전환을 명확히 유도

## 2) Frame / Grid
- Desktop Frame: `1440 x 1024`
- Content Max Width: `1200`
- Grid: `12 columns`, Margin `120`, Gutter `24`
- Section Vertical Spacing: `24 / 32 / 40` 체계

## 3) 상단 구조
- Top Navigation 높이: `56`
- 버튼 4개:
  - `홈`
  - `1. 입시위치 진단`
  - `2. AI탐구·세특`
  - `3. 컨설팅 신청`
- 버튼 Radius: `10`
- 버튼 최소 높이: `42`

## 4) Hero 영역
- 배경: 다크 블루 그라데이션
  - 시작 `#0B1E41`
  - 끝 `#1A4A9A`
- Radius: `14`
- Padding: `20`
- Title: `서비스 통합 포털`
- Sub: `원하는 서비스를 바로 선택해 시작하세요.`

## 5) 3구역 카드 영역
- 3열 동일 폭 카드
- 카드 높이(최소): `220`
- 카드 Radius: `16`
- 카드 Border: `1px #DCE5F5`
- 카드 배경: `#F8FBFF -> #F3F8FF` 세로 그라데이션
- 카드 내부 구성:
  - Chip (`01/02/03`)
  - Title
  - Description
  - CTA Button

### 카드 텍스트
- 카드 1
  - 제목: `나의 입시 위치 진단`
  - 설명: `학생부 분석과 합격컷 기반의 진단 서비스`
  - 버튼: `1번 서비스 열기`
- 카드 2
  - 제목: `AI탐구·세특 생성기`
  - 설명: `교과/진로 기반 탐구 주제 추천 및 세특 문장 생성`
  - 버튼: `2번 서비스 열기`
- 카드 3
  - 제목: `대치수프리마 입시 컨설팅 신청`
  - 설명: `상담 신청 접수 및 후속 연락`
  - 버튼: `3번 서비스 열기`

## 6) 서비스 내부 공통 바로가기 바
- 타이틀: `서비스 안내 및 바로가기`
- 3열 블록:
  - `1. 나의 입시 위치 진단` 이동 버튼
  - `2. AI탐구·세특 생성기` 이동 버튼
  - `3. 대치수프리마 입시 컨설팅 신청` 이동 버튼
- 현재 보고 있는 서비스는 버튼 대신 상태 배지(`현재 이용 중`) 표시

## 7) Typography
- 한글 기본: `Pretendard` (Fallback: `Noto Sans KR`, `sans-serif`)
- Hero Title: `30 / 800`
- Card Title: `24 / 800`
- Body: `14 / 500~600`
- Caption: `12 / 500`

## 8) Color Tokens
- `primary-900`: `#0B1E41`
- `primary-700`: `#1A4A9A`
- `primary-100`: `#E8F0FF`
- `text-strong`: `#0B1F42`
- `text-sub`: `#2F4469`
- `line-soft`: `#DCE5F5`
- `surface-0`: `#FFFFFF`
- `surface-1`: `#F8FBFF`

## 9) 인터랙션
- Hover: 카드 그림자 + 버튼 밝기 소폭 증가
- Active: 버튼 살짝 눌림(`translateY(1px)`)
- Transition: `160ms ease-out`

## 10) 반응형
- Tablet (`<=1024`): 2열 + 1열
- Mobile (`<=768`): 1열 스택
- 모바일에서 버튼 Full Width 유지

## 11) 접근성
- 텍스트 대비 4.5:1 이상
- 클릭 타겟 최소 높이 `40+`
- 포커스 링 명확히 표시 (`outline` or `box-shadow`)

