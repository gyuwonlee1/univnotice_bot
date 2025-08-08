import requests
from bs4 import BeautifulSoup
import os
import re # 자바스크립트 링크에서 숫자 추출을 위해 추가

# -------------------------------------------------------------------
# ✨ 여기만 수정하면 돼! 알림 받고 싶은 홈페이지 목록 ✨
# -------------------------------------------------------------------
TARGET_SITES = [
    {
        'name': '서울대학교 경제학부',
        'url': 'https://econ.snu.ac.kr/announcement/notice',
        'base_url': 'https://econ.snu.ac.kr',
        'selector': 'tr.noti .title a',
        # ✨ 경제학부 전용 '링크 조립 설명서' 추가
        'link_format': '/announcement/notice?bm=v&bbsidx={idx}',
    },
    {
        'name': '서울대학교 인공지능 연합전공',
        'url': 'https://imai.snu.ac.kr/category/board-21-GN-n5xFXM59-20210303165043/',
        'base_url': '',
        'selector': 'li:not(:has(span.notice)) .subject a',
        # ✨ 인공지능 연합전공 전용 '링크 조립 설명서' 추가
        'link_format': 'https://imai.snu.ac.kr/category/board-21-GN-n5xFXM59-20210303165043/?uid={idx}&mod=document',
    },
    # 여기에 계속 추가할 수 있어!
]

# Discord 웹훅 URL은 GitHub Actions의 Secrets에서 자동으로 가져옴
webhook_url = os.environ.get('DISCORD_WEBHOOK_URL')

def send_discord_message(text):
    """디스코드로 메시지를 보내는 함수"""
    if not webhook_url:
        print("디스코드 웹훅 URL이 설정되지 않았어. 로컬 테스트 모드로 실행할게.")
        print(f"보낼 메시지:\n{text}\n")
        return

    data = {"content": text}
    response = requests.post(webhook_url, json=data)
    if response.status_code == 204:
        print("디스코드 메시지 전송 성공!")
    else:
        print(f"디스코드 메시지 전송 실패: {response.status_code}")

def crawl_and_notify():
    """홈페이지 목록을 돌면서 최신 공지를 확인하고 알림을 보내는 함수 (업그레이드 버전)"""
    print("📢 전체 공지사항 확인을 시작합니다...")
    
    for site in TARGET_SITES:
        site_name = site['name']
        print(f"--- [{site_name}] 확인 중 ---")

        try:
            response = requests.get(site['url'], headers={'User-Agent': 'Mozilla/5.0'})
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            latest_notice = soup.select_one(site['selector'])

            if latest_notice:
                title = latest_notice.get_text(strip=True)
                link = latest_notice.get('href', '#')

                # --- ✨ 링크 주소 처리 로직 시작 (여기가 핵심!) ✨ ---
                
                # 1. 자바스크립트 링크 처리 (onclick)
                if '#none' in link or '#' == link:
                    onclick_attr = latest_notice.get('onclick', '')
                    board_idx_match = re.search(r"go_board_view\('(\d+)'\)", onclick_attr)
                    if board_idx_match:
                        board_idx = board_idx_match.group(1)
                        # ✨ 해당 사이트의 'link_format' 설명서를 보고 링크를 조립하도록 수정
                        if site.get('link_format'):
                            link = site['link_format'].format(idx=board_idx)

                # 2. 상대 경로 처리 (base_url 붙여주기)
                if site['base_url'] and link.startswith('/'):
                    link = site['base_url'] + link

                # --- 링크 주소 처리 로직 끝 ---

                message = f"📢 **[{site_name}]** 새 공지!\n\n**{title}**\n{link}"
                send_discord_message(message)
            else:
                print(f"[{site_name}]에서 새 공지를 찾지 못했어.")

        except requests.RequestException as e:
            print(f"[{site_name}] 접속 오류가 발생했어: {e}")
        except Exception as e:
            print(f"[{site_name}] 처리 중 알 수 없는 오류가 발생했어: {e}")
        
        print(f"--- [{site_name}] 확인 완료 ---\n")

# 이 스크립트 파일을 직접 실행했을 때만 함수를 실행
if __name__ == "__main__":

    crawl_and_notify()
