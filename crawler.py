import requests
from bs4 import BeautifulSoup
import os

# -------------------------------------------------------------------
# ✨ 여기만 수정하면 돼! 알림 받고 싶은 홈페이지 목록 ✨
# -------------------------------------------------------------------
# 아래 형식에 맞춰서 원하는 만큼 홈페이지를 추가하거나 수정해줘.
# 
# 'name': 디스코드에 표시될 홈페이지 이름
# 'url': 공지사항 목록 페이지의 전체 주소
# 'base_url': 공지 링크가 일부만 있을 때(예: /board/123) 앞에 붙여줄 주소.
#             링크가 처음부터 완전한 주소(https://...)라면 비워둬도 돼.
# 'selector': 공지사항 제목을 찾는 CSS 선택자
# -------------------------------------------------------------------
TARGET_SITES = [
    {
        'name': '서울대학교 경제학부',
        'url': 'https://econ.snu.ac.kr/announcement/notice',
        'base_url': '',
        'selector': 'tr.noti .title a',
    },
    {
        'name': '서울대학교 인공지능 연합전공',
        'url': 'https://imai.snu.ac.kr/category/board-21-GN-n5xFXM59-20210303165043/',
        'base_url': '',
        'selector': 'li:not(:has(span.notice)) .subject a',
    },
    # 여기에 계속 추가할 수 있어! 아래 주석을 풀고 내용을 채워봐.
    # {
    #     'name': '추가할 홈페이지 이름',
    #     'url': 'https://....',
    #     'base_url': 'https://....',
    #     'selector': '...',
    # },
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
    """홈페이지 목록을 돌면서 최신 공지를 확인하고 알림을 보내는 함수"""
    print("📢 전체 공지사항 확인을 시작합니다...")
    
    # TARGET_SITES 목록에 있는 각 홈페이지를 하나씩 확인
    for site in TARGET_SITES:
        site_name = site['name']
        print(f"--- [{site_name}] 확인 중 ---")

        try:
            response = requests.get(site['url'], headers={'User-Agent': 'Mozilla/5.0'})
            response.raise_for_status() # 접속 오류가 있으면 예외 발생
            soup = BeautifulSoup(response.text, 'html.parser')

            # CSS 선택자로 가장 최신 공지사항 1개만 선택
            latest_notice = soup.select_one(site['selector'])

            if latest_notice:
                title = latest_notice.get_text(strip=True)
                # get('href', '#')는 href 속성이 없는 경우를 대비한 안전장치
                link = latest_notice.get('href', '#')

                # 링크가 완전한 주소가 아닐 경우, base_url을 앞에 붙여줌
                if site['base_url'] and not link.startswith('http'):
                    link = site['base_url'] + link

                # ✨ 디스코드 메시지에 홈페이지 이름을 포함하도록 수정!
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