import requests
from bs4 import BeautifulSoup
import os
import re
import json 
import time
from urllib.parse import urljoin

TARGET_SITES = [
    {
        'name': '서울대학교 경제학부',
        'url': 'https://econ.snu.ac.kr/announcement/notice',
        'base_url': 'https://econ.snu.ac.kr',
        'selectors': [
            'tr.noti .title a',
            'table a[href*="bbsidx="]',
        ],
        'link_allow_patterns': [
            r'bbsidx=\d+',
        ],
    },
    {
        'name': '서울대학교 인공지능 연합전공',
        'url': 'https://imai.snu.ac.kr/category/board-21-GN-n5xFXM59-20210303165043/',
        'base_url': '',
        'link_format': 'https://imai.snu.ac.kr/category/board-21-GN-n5xFXM59-20210303165043/?uid={idx}&mod=document',
        'selectors': [
            # 사이트 구조가 자주 변할 수 있어, 가능한 폭넓게 후보를 둠
            'a[href*="uid="]',
            'table a',
            'article a',
            'a',
        ],
        'link_allow_patterns': [
            r'uid=\d+',
            r'mod=document',
        ],
    },
    {
        'name': '서울대학교 경영대학', 
        'url': 'https://cba.snu.ac.kr/newsroom/notice',
        'base_url': 'https://cba.snu.ac.kr',
        'selectors': [
            'tr.noti .title a',
            'table a[href*="bbsidx="]',
        ],
        'link_allow_patterns': [
            r'bbsidx=\d+',
        ],
    },
]

LATEST_LINKS_FILE = 'latest_links.json'
webhook_url = os.environ.get('DISCORD_WEBHOOK_URL')
DEBUG_DIR = os.environ.get('DEBUG_HTML_DIR', 'debug_html')
DEBUG_SAVE_HTML = os.environ.get('DEBUG_SAVE_HTML', '1') == '1'
MIN_NOTICE_COUNT = int(os.environ.get('MIN_NOTICE_COUNT', '3'))
REQUEST_TIMEOUT_SECONDS = int(os.environ.get('REQUEST_TIMEOUT_SECONDS', '20'))
MAX_DEBUG_HTML_BYTES = int(os.environ.get('MAX_DEBUG_HTML_BYTES', str(2_000_000)))
FAIL_ON_SITE_FAILURE = os.environ.get('FAIL_ON_SITE_FAILURE', '0') == '1'
MAX_STORED_LINKS_PER_SITE = int(os.environ.get('MAX_STORED_LINKS_PER_SITE', '200'))
MAX_SEND_PER_SITE_PER_RUN = int(os.environ.get('MAX_SEND_PER_SITE_PER_RUN', '20'))

def send_discord_message(text):
    """디스코드로 메시지를 보내는 함수"""
    if not webhook_url:
        print("디스코드 웹훅 URL이 설정되지 않았어. 로컬 테스트 모드로 실행할게.")
        # Windows 콘솔(cp949 등)에서 이모지/특수문자가 있을 때도 크래시가 나지 않도록 안전 출력
        try:
            safe_text = text.encode("cp949", errors="backslashreplace").decode("cp949", errors="replace")
        except Exception:
            safe_text = str(text)
        print(f"보낼 메시지:\n{safe_text}\n")
        return

    data = {"content": text}
    response = requests.post(webhook_url, json=data)
    if response.status_code == 204:
        print("디스코드 메시지 전송 성공!")
    else:
        print(f"디스코드 메시지 전송 실패: {response.status_code}")

def send_discord_warning(site_name: str, reason: str, extra: str = ""):
    message = f"[WARN] **[{site_name}]** 크롤링 경고\n\n- 이유: {reason}"
    if extra:
        message += f"\n- 추가정보: {extra}"
    send_discord_message(message)

def load_latest_links():
    """파일에 저장된 '마지막 공지 링크'를 불러오는 함수"""
    try:
        with open(LATEST_LINKS_FILE, 'r') as f:
            data = json.load(f)
            # 마이그레이션 지원:
            # - legacy: {site: "single_link"}  (이 경우 기존 break 로직을 1회 유지)
            # - v2:     {site: ["link1", "link2", ...]} (set 기반 중복 방지)
            legacy_anchors = {}
            migrated = {}
            if isinstance(data, dict):
                for k, v in data.items():
                    if isinstance(v, list):
                        migrated[k] = [x for x in v if isinstance(x, str)]
                    elif isinstance(v, str):
                        legacy_anchors[k] = v
                        migrated[k] = [v]  # 최소한 anchor는 seen에 포함
                    else:
                        migrated[k] = []
            return migrated, legacy_anchors
    except FileNotFoundError:
        return {}, {}

def save_latest_links(links):
    """사이트별 '최근에 본 공지 링크 목록'을 파일에 저장하는 함수"""
    with open(LATEST_LINKS_FILE, 'w') as f:
        json.dump(links, f, indent=4)

def _safe_site_slug(site_name: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z가-힣_-]+", "_", site_name).strip("_")
    return slug or "site"

def save_debug_html(site_name: str, url: str, html_text: str, suffix: str):
    if not DEBUG_SAVE_HTML:
        return
    try:
        os.makedirs(DEBUG_DIR, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S", time.localtime())
        slug = _safe_site_slug(site_name)
        filename = f"{slug}_{ts}_{suffix}.html"
        path = os.path.join(DEBUG_DIR, filename)
        data = html_text.encode("utf-8", errors="replace")
        if len(data) > MAX_DEBUG_HTML_BYTES:
            data = data[:MAX_DEBUG_HTML_BYTES]
        with open(path, "wb") as f:
            f.write(data)
        print(f"[{site_name}] 디버그 HTML 저장: {path} (url={url})")
    except Exception as e:
        print(f"[{site_name}] 디버그 HTML 저장 실패: {e}")

def _looks_like_blocked_or_wrong_page(text: str) -> bool:
    lowered = text.lower()
    suspicious = [
        "access denied",
        "forbidden",
        "cloudflare",
        "cf-challenge",
        "cf-turnstile",
        "g-recaptcha",
        "hcaptcha",
        "권한이 없습니다",
        "접근이 제한",
    ]
    return any(s in lowered for s in suspicious)

def extract_notice_anchors(site: dict, soup: BeautifulSoup):
    selectors = site.get("selectors") or []
    anchors = []
    seen = set()

    for sel in selectors:
        try:
            for a in soup.select(sel):
                if not a or a.name != "a":
                    continue
                href = a.get("href")
                if not href:
                    continue
                key = (a.get_text(strip=True), href)
                if key in seen:
                    continue
                seen.add(key)
                anchors.append(a)
        except Exception:
            continue

    # 그래도 없으면 전체 a로 fallback (구조 변경 대응)
    if not anchors:
        for a in soup.find_all("a"):
            href = a.get("href")
            if not href:
                continue
            key = (a.get_text(strip=True), href)
            if key in seen:
                continue
            seen.add(key)
            anchors.append(a)

    return anchors

def normalize_and_filter_notices(site: dict, anchors):
    allow_patterns = [re.compile(p) for p in site.get("link_allow_patterns") or []]
    notices = []

    for a in anchors:
        title = a.get_text(strip=True)
        href = a.get("href", "")

        if not title:
            continue

        # href가 비정상인 케이스 처리 (기존 로직 유지)
        if "#none" in href or href == "#":
            onclick_attr = a.get("onclick", "")
            board_idx_match = re.search(r"go_board_view\('(\d+)'\)", onclick_attr)
            if board_idx_match:
                board_idx = board_idx_match.group(1)
                if site.get("link_format"):
                    href = site["link_format"].format(idx=board_idx)

        # 절대경로 변환
        base_url = site.get("base_url") or site.get("url") or ""
        link = urljoin(base_url, href)

        # 너무 광범위한 링크는 필터링 (메뉴/푸터 등)
        if allow_patterns:
            if not any(p.search(link) for p in allow_patterns):
                continue

        notices.append({"title": title, "link": link})

    return notices

def crawl_and_notify():
    """홈페이지 목록을 돌면서 '새로운' 공지만 확인하고 알림을 보내는 함수"""
    print("[INFO] 전체 공지사항 확인을 시작합니다...")
    
    latest_links, legacy_anchors = load_latest_links()
    new_announcement_found = False
    site_failures = []
    site_warnings = []

    for site in TARGET_SITES:
        site_name = site['name']
        print(f"--- [{site_name}] 확인 중 ---")

        try:
            response = requests.get(
                site['url'],
                headers={'User-Agent': 'Mozilla/5.0'},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            if _looks_like_blocked_or_wrong_page(response.text):
                save_debug_html(site_name, site["url"], response.text, "blocked_or_wrong")
                send_discord_warning(site_name, "차단/로그인/비정상 페이지로 보임", f"url={site['url']}")
                site_failures.append((site_name, "blocked_or_wrong"))
                continue
            soup = BeautifulSoup(response.text, 'html.parser')
            
            anchors = extract_notice_anchors(site, soup)
            all_notices = normalize_and_filter_notices(site, anchors)

            if len(all_notices) < MIN_NOTICE_COUNT:
                # 구조 변경/selector 실패 가능성이 높아서 증거 확보 + 경고
                save_debug_html(site_name, site["url"], response.text, f"too_few_{len(all_notices)}")
                send_discord_warning(
                    site_name,
                    "공지 추출 개수가 너무 적음(구조 변경 가능)",
                    f"count={len(all_notices)} (min={MIN_NOTICE_COUNT}), url={site['url']}",
                )
                site_warnings.append((site_name, f"too_few_{len(all_notices)}"))
                # 그래도 1개라도 있으면 “새 공지” 체크는 진행 (완전 중단 대신 부분 동작)
                if not all_notices:
                    site_failures.append((site_name, "zero_notices"))
                    continue

           
            seen_links_list = latest_links.get(site_name) or []
            if not isinstance(seen_links_list, list):
                seen_links_list = [seen_links_list] if isinstance(seen_links_list, str) else []
            seen_links = set([x for x in seen_links_list if isinstance(x, str)])

            new_notices_to_send = []

            # legacy 상태였으면 "anchor까지 break" 방식으로 1회만 기존 동작을 유지 (알림 폭탄 방지)
            legacy_anchor = legacy_anchors.get(site_name)
            if legacy_anchor:
                for notice in all_notices:
                    link = notice["link"]
                    if link == legacy_anchor:
                        break
                    new_notices_to_send.append({'title': notice["title"], 'link': link})
            else:
                # v2: 이번에 긁은 링크 중 "처음 보는 것"만 추림
                for notice in all_notices:
                    link = notice["link"]
                    if link in seen_links:
                        continue
                    new_notices_to_send.append({'title': notice["title"], 'link': link})

                # 안전장치: 첫 실행(또는 상태 유실)로 seen이 비어있을 때는 전송하지 않고 기준만 저장
                is_first_baseline = len(seen_links) == 0
                if is_first_baseline:
                    baseline_links = []
                    for n in all_notices:
                        baseline_links.append(n["link"])
                        if len(baseline_links) >= MAX_STORED_LINKS_PER_SITE:
                            break
                    latest_links[site_name] = baseline_links
                    new_announcement_found = True  # 상태 저장 필요
                    print(f"[INFO] [{site_name}] 초기 기준선 저장만 수행 (send=0, stored={len(baseline_links)})")
                    continue


            if new_notices_to_send:
                # 너무 많이 보내는 것을 방지
                total_new = len(new_notices_to_send)
                if total_new > MAX_SEND_PER_SITE_PER_RUN:
                    save_debug_html(site_name, site["url"], response.text, f"too_many_new_{total_new}")
                    send_discord_warning(
                        site_name,
                        "새 공지가 너무 많아 일부만 전송(상태 유실/구조 변경 가능)",
                        f"new={total_new}, send_cap={MAX_SEND_PER_SITE_PER_RUN}, url={site['url']}",
                    )
                    site_warnings.append((site_name, f"too_many_new_{total_new}"))
                    new_notices_to_send = new_notices_to_send[:MAX_SEND_PER_SITE_PER_RUN]

                print(f"[NEW] [{site_name}] 새로운 공지 {len(new_notices_to_send)}건 발견")
                new_announcement_found = True
                

                # 상태 업데이트: 새 링크를 앞에 붙이고, 기존 seen과 합쳐서 중복 제거 + 용량 제한
                updated = [n["link"] for n in new_notices_to_send] + list(seen_links_list)
                deduped = []
                deduped_set = set()
                for link in updated:
                    if not isinstance(link, str):
                        continue
                    if link in deduped_set:
                        continue
                    deduped_set.add(link)
                    deduped.append(link)
                    if len(deduped) >= MAX_STORED_LINKS_PER_SITE:
                        break
                latest_links[site_name] = deduped
                

                # 오래된 것부터 보내기 위해 reverse
                new_notices_to_send.reverse()
                
                for notice_data in new_notices_to_send:
                    message = f"📢 **[{site_name}]** 새 공지!\n\n# {notice_data['title']}\n{notice_data['link']}"
                    send_discord_message(message)
            else:
                print("[SKIP] 이미 보냈던 공지입니다. 알림을 보내지 않습니다.")

        except requests.RequestException as e:
            save_debug_html(site_name, site["url"], getattr(locals().get("response", None), "text", "") or "", "request_exception")
            print(f"[{site_name}] 접속 오류가 발생했어: {e}")
            send_discord_warning(site_name, "접속/HTTP 오류", str(e))
            site_failures.append((site_name, "request_exception"))
        except Exception as e:
            save_debug_html(site_name, site["url"], getattr(locals().get("response", None), "text", "") or "", "unknown_exception")
            print(f"[{site_name}] 처리 중 알 수 없는 오류가 발생했어: {e}")
            send_discord_warning(site_name, "알 수 없는 오류", str(e))
            site_failures.append((site_name, "unknown_exception"))
        
        print(f"--- [{site_name}] 확인 완료 ---\n")
    
    if new_announcement_found:
        print("[INFO] 새로운 공지 목록을 파일에 저장합니다.")
        save_latest_links(latest_links)
    else:
        print("[INFO] 변경된 내용이 없어 파일을 업데이트하지 않습니다.")

    if site_warnings:
        print("[WARN] 사이트 경고 요약:")
        for name, reason in site_warnings:
            print(f"  - {name}: {reason}")

    if site_failures:
        print("[ERROR] 사이트 실패 요약:")
        for name, reason in site_failures:
            print(f"  - {name}: {reason}")
        if FAIL_ON_SITE_FAILURE:
            raise SystemExit(2)

if __name__ == "__main__":

    crawl_and_notify()
