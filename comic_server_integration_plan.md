# JoyViewer - 코믹 서버(Comic Server) 연동 기능 구현 설계서

JoyViewer v4.1에 원격 코믹 서버(OPDS, Komga, Kavita, WebDAV 등)와의 연결 기능을 추가하기 위한 기술적 요구사항 및 아키텍처 구현 계획입니다. 이 기능을 통해 사용자는 로컬 디렉토리뿐만 아니라 자가 호스팅(Self-hosted) 중인 원격 서재의 웹툰 및 만화책 데이터를 실시간 스트리밍으로 감상할 수 있게 됩니다.

---

## 1. 아키텍처 개요 (Architecture Overview)

원격 코믹 서버 연동은 JoyViewer의 파이썬 백엔드(`webtoon_viewer.py`)가 프록시(Proxy) 역할을 수행하고, 프론트엔드(자바스크립트 SPA)는 기존의 로컬 인터페이스와 동일한 흐름으로 데이터를 렌더링할 수 있도록 설계합니다.

```{mermaid}
graph TD
    subgraph Frontend [프론트엔드 자바스크립트]
        UI[사이드바 / 뷰어 UI] -->|API 요청| WebApi[ApiWrapper]
    end

    subgraph Backend [파이썬 Bottle 백엔드]
        WebApi -->|로컬 요청| LocalReader[로컬 웹툰 리더]
        WebApi -->|원격 요청| ServerManager[원격 코믹 서버 매니저]
        ServerManager -->|데이터 프록시 및 캐싱| ImageProxy[이미지 캐시 매니저]
    end

    subgraph RemoteServers [원격 코믹 서버]
        ServerManager -->|OPDS Protocol| OPDS[Ubooquity / Calibre]
        ServerManager -->|REST API| Komga[Komga / Kavita]
        ServerManager -->|WebDAV| WebDAV[NAS / WebDAV]
    end
```

---

## 2. 연동 지원 대상 프로토콜

코믹/웹소설 서재 서비스에서 널리 쓰이는 표준 규격 및 유명 자가 호스팅 API를 우선순위별로 지원합니다.

| 우선순위 | 서버 구분 | 통신 방식 (Protocol) | 주요 특징 |
| :--- | :--- | :--- | :--- |
| **1순위** | **Komga / Kavita** | REST API | 대표적인 만화책/웹툰 자가호스팅 서버. 페이징 및 책갈피 양방향 동기화 최적화 |
| **2순위** | **OPDS 표준** | XML/Atom 피드 | Ubooquity, Calibre 등 표준화된 전자책 카탈로그 스트리밍 규격 |
| **3순위** | **WebDAV** | HTTP XML | Synology NAS 등 개인 서버 내 압축 파일(.cbz) 및 폴더를 다이렉트 스트리밍 |

---

## 3. 상세 구현 단계 (Implementation Steps)

### 단계 1: 백엔드 접속 정보 영속화 (`joyviewer_config.json`)
서버 추가 시 접속 정보가 손실되지 않도록 기존 설정 파일 구조를 확장합니다. 보안을 위해 비밀번호는 암호화(Base64 또는 AES) 처리하여 저장합니다.

```json
{
    "scrollMode": "step",
    "remote_servers": [
        {
            "id": "srv_komga_01",
            "name": "내 방 Komga 서버",
            "type": "komga",
            "url": "http://192.168.1.100:8080",
            "username": "my_email@domain.com",
            "password": "encrypted_password_base64_=="
        }
    ]
}
```

### 단계 2: 원격 연동 파이썬 인터페이스 개발 (`ComicServerClient` 클래스)
원격 프로토콜을 추상화하여, 프론트엔드 요청에 맞춰 서재 목록(Webtoons)과 에피소드(Episodes), 이미지 목록(Images)을 반환하는 백엔드 코어 클래스를 설계합니다.

```python
class ComicServerClient:
    def __init__(self, config):
        self.server_type = config['type']
        self.url = config['url']
        self.auth = (config['username'], self.decrypt_pw(config['password']))

    def get_library(self):
        """서재 목록(웹툰 및 만화책 리스트) 호출"""
        if self.server_type == 'komga':
            return self._fetch_komga_series()
        elif self.server_type == 'opds':
            return self._fetch_opds_catalogs()
        return []

    def get_episodes(self, series_id):
        """시리즈 하위의 단권/화차 목록 호출"""
        pass

    def get_images(self, book_id):
        """선택한 단권의 이미지 URL 목록 또는 실시간 압축 해제 스트림 반환"""
        pass
```

### 단계 3: Bottle 라우팅 프록시(API) 개설
원격 이미지나 데이터 스트리밍 시, 브라우저의 CORS 제한 및 원격 세션 만료를 우회할 수 있도록 **백엔드 프록시 API**를 생성합니다.

```python
@app.route('/api/remote/image')
def api_remote_image_proxy():
    server_id = request.query.server_id
    image_url = request.query.url
    
    # 1. 로컬 캐시 디렉토리에 원격 이미지가 존재하면 즉시 반환 (성능 극대화)
    cache_path = get_local_cache_path(server_id, image_url)
    if os.path.exists(cache_path):
        return static_file(cache_path)

    # 2. 캐시가 없으면 원격 서버에 요청하여 이미지를 받아와 캐시 저장 후 반환
    img_data = download_remote_image(server_id, image_url)
    save_to_cache(cache_path, img_data)
    
    response.content_type = 'image/jpeg'
    return img_data
```

### 단계 4: 프론트엔드 UI/UX 설계
기존의 미려하고 반응성이 뛰어난 JoyViewer 테마를 그대로 유지하며, 원격 서버를 손쉽게 추가하고 탐색할 수 있는 메뉴를 확장합니다.

1.  **사이드바 최상단 [웹툰폴더+] 버튼 옆 [원격서버+] 버튼 추가**:
    *   버튼 클릭 시 모달창(Modal Popup)을 띄워 서버 타입(Komga, Kavita, OPDS), 서버 이름, 주소, 로그인 정보를 입력받아 보관합니다.
2.  **원격 라이브러리 목록 렌더링**:
    *   사이드바에 **[내 서재 (로컬)]**과 **[원격 서재 (서버 이름)]** 카테고리를 분리해 배치합니다.
    *   원격 서버 카드는 우측 상단에 작은 원격 네트워크 아이콘(🌐)을 표시하여 구별합니다.

```javascript
// 프론트엔드 서버 연동 시각화 목업
function renderLibrary(webtoons) {
    const wrapper = document.getElementById('webtoon-items-wrapper');
    webtoons.forEach(wt => {
        const isRemote = wt.is_remote ? '🌐' : '';
        const card = `
            <div class="webtoon-card" onclick="selectWebtoon('${wt.path}', '${wt.name}')">
                <span class="remote-badge">${isRemote}</span>
                <img src="${wt.thumbnail}">
                <div class="info">${wt.name}</div>
            </div>
        `;
        wrapper.innerHTML += card;
    });
}
```

---

## 4. 기대 효과 및 고려 사항

### 🚀 기대 효과
*   **스트리밍 감상**: 모바일 및 PC 등 하드 용량이 부족한 기기에서도 기가바이트(GB) 단위의 대용량 고화질 만화책 및 웹툰을 실시간으로 감상 가능.
*   **통합 뷰어 진화**: 로컬 파일 리더에 머물지 않고, 자가 호스팅 에코시스템(Ubooquity, Komga 등)을 아우르는 완벽한 크로스 플랫폼 웹툰 클라이언트로 도약.

### ⚠️ 기술적 고려 사항
*   **로컬 캐싱 최적화 (가장 중요)**: 모바일 스트리밍 시 버퍼링을 없애기 위해, 사용자가 현재 페이지를 읽는 동안 **백그라운드 스레드에서 다음 2~3장의 이미지를 원격 서버로부터 선제적으로 프록시 캐시(Pre-fetching)** 하는 엔진이 필수적으로 탑재되어야 함.
*   **세션 보안**: 비밀번호 정보를 로컬 파일에 투명하게 보관하지 않도록 운영체제 보안 키체인을 활용하거나 적절한 암호화 알고리즘 처리가 필요.
