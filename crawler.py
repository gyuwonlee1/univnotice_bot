import requests
from bs4 import BeautifulSoup
import os
import re
import json 

TARGET_SITES = [
    {
        'name': '서울대학교 경제학부',
        'url': 'https://econ.snu.ac.kr/announcement/notice',
        'base_url': 'https://econ.snu.ac.kr',
        'selector': 'tr.noti .title a',
    },
    {
        'name': '서울대학교 인공지능 연합전공',
        'url': 'https://imai.snu.ac.kr/category/board-21-GN-n5xFXM59-20210303165043/',
        'base_url': '',
        'selector': 'li:not(:has(span.notice)) .subject a',
        'link_format': 'https://imai.snu.ac.kr/category/board-21-GN-n5xFXM59-20210303165043/?uid={idx}&mod=document',
    },
    {
        'name': '서울대학교 경영대학', 
        'url': 'https://cba.snu.ac.kr/newsroom/notice',
        'base_url': 'https://cba.snu.ac.kr',
        'selector': 'tr.noti .title a',
    },
]

LATEST_LINKS_FILE = 'latest_links.json'
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

def load_latest_links():
    """파일에 저장된 '마지막 공지 링크'를 불러오는 함수"""
    try:
        with open(LATEST_LINKS_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_latest_links(links):
    """'마지막 공지 링크'를 파일에 저장하는 함수"""
    with open(LATEST_LINKS_FILE, 'w') as f:
        json.dump(links, f, indent=4)

def crawl_and_notify():
    """홈페이지 목록을 돌면서 '새로운' 공지만 확인하고 알림을 보내는 함수"""
    print("📢 전체 공지사항 확인을 시작합니다...")
    
    latest_links = load_latest_links()
    new_announcement_found = False

    for site in TARGET_SITES:
        site_name = site['name']
        print(f"--- [{site_name}] 확인 중 ---")

        try:
            response = requests.get(site['url'], headers={'User-Agent': 'Mozilla/5.0'})
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
           
            all_notices = soup.select(site['selector'])
            
            if not all_notices:
                print(f"[{site_name}]에서 공지를 찾지 못했어.")
                continue

           
            previous_link = latest_links.get(site_name)
            new_notices_to_send = []

            for notice in all_notices:
                title = notice.get_text(strip=True)
                link = notice.get('href', '#')

               
                if '#none' in link or '#' == link:
                    onclick_attr = notice.get('onclick', '')
                    board_idx_match = re.search(r"go_board_view\('(\d+)'\)", onclick_attr)
                    if board_idx_match:
                        board_idx = board_idx_match.group(1)
                        if site.get('link_format'):
                            link = site['link_format'].format(idx=board_idx)
                
                if site['base_url'] and link.startswith('/'):
                    link = site['base_url'] + link
                
              
                if link == previous_link:
                    break
                
                new_notices_to_send.append({'title': title, 'link': link})


            if new_notices_to_send:
                print(f"✨ [{site_name}]에서 {len(new_notices_to_send)}개의 새로운 공지를 발견했습니다!")
                new_announcement_found = True
                

                latest_links[site_name] = new_notices_to_send[0]['link']
                

                new_notices_to_send.reverse()
                
                for notice_data in new_notices_to_send:
                    message = f"📢 **[{site_name}]** 새 공지!\n\n# {notice_data['title']}\n{notice_data['link']}"
                    send_discord_message(message)
            else:
                print("🤔 이미 보냈던 공지입니다. 알림을 보내지 않습니다.")

        except requests.RequestException as e:
            print(f"[{site_name}] 접속 오류가 발생했어: {e}")
        except Exception as e:
            print(f"[{site_name}] 처리 중 알 수 없는 오류가 발생했어: {e}")
        
        print(f"--- [{site_name}] 확인 완료 ---\n")
    
    if new_announcement_found:
        print("💾 새로운 공지 목록을 파일에 저장합니다.")
        save_latest_links(latest_links)
    else:
        print("✅ 변경된 내용이 없어 파일을 업데이트하지 않습니다.")

if __name__ == "__main__":

    crawl_and_notify()
