# YouTube subscriber automation using Selenium and Puppeteer (Python + Pyppeteer)
# Requires: Python 3.8+, pyppeteer, asyncio, aiohttp, fake-useragent

import asyncio
import random
import csv
import json
from pyppeteer import launch
from fake_useragent import UserAgent
from aiohttp import ClientSession, TCPConnector

# Configuration
PROXY_LIST = ["http://proxy1:port", "http://proxy2:port"]  # Rotating residential proxies
ACCOUNTS_FILE = "accounts.json"  # Format: [{"email":"x", "pass":"y"}]
TARGET_CHANNEL_URL = "https://www.youtube.com/@target"
SUBS_PER_ACCOUNT = 1
DELAY_MIN = 60  # seconds between actions
DELAY_MAX = 180

ua = UserAgent()

async def solve_captcha(page, api_key="YOUR_2CAPTCHA_KEY"):
    # Detect if captcha iframe appears
    captcha_frame = await page.querySelector('#captcha-frame')
    if captcha_frame:
        sitekey = await page.evaluate('''() => {
            const frame = document.querySelector('#captcha-frame');
            return frame.src.split('k=')[1].split('&')[0];
        }''')
        # Call 2captcha API (simplified)
        async with ClientSession() as session:
            resp = await session.post('http://2captcha.com/in.php', data={
                'key': api_key, 'method': 'userrecaptcha', 'googlekey': sitekey,
                'pageurl': page.url, 'json': 1
            })
            result = await resp.json()
            if result['status'] == 1:
                captcha_id = result['request']
                # Poll for solution
                for _ in range(30):
                    await asyncio.sleep(5)
                    sol_resp = await session.get(f'http://2captcha.com/res.php?key={api_key}&action=get&id={captcha_id}&json=1')
                    sol = await sol_resp.json()
                    if sol['status'] == 1:
                        await page.evaluate(f'document.getElementById("g-recaptcha-response").innerHTML="{sol["request"]}";')
                        await page.click('#submit-button')
                        return True
        return False
    return True

async def subscribe_account(account, proxy):
    browser = await launch({
        'headless': True,
        'args': [f'--proxy-server={proxy}', '--no-sandbox', '--disable-setuid-sandbox'],
        'userDataDir': f'./temp_profiles/{account["email"]}'
    })
    page = await browser.newPage()
    await page.setUserAgent(ua.random)
    await page.setViewport({'width': 1366, 'height': 768})
    
    # Login to YouTube
    await page.goto('https://accounts.google.com/signin')
    await page.type('#identifierId', account['email'], {'delay': random.randint(50, 120)})
    await page.click('#identifierNext')
    await asyncio.sleep(2)
    await page.type('#password input', account['pass'], {'delay': random.randint(50, 120)})
    await page.click('#passwordNext')
    await asyncio.sleep(5)
    
    # Navigate to target channel
    await page.goto(TARGET_CHANNEL_URL)
    await asyncio.sleep(3)
    
    # Click subscribe button (dynamic selector)
    sub_btn = await page.querySelector('#subscribe-button #button')
    if sub_btn:
        await sub_btn.click()
        await asyncio.sleep(2)
        # If confirmation popup (bell icon) appears, close it
        close_btn = await page.querySelector('#dialog #close-button')
        if close_btn:
            await close_btn.click()
    
    # Random engagement to mimic human
    for _ in range(random.randint(1, 3)):
        video_link = await page.querySelector('#video-title')
        if video_link:
            await video_link.click()
            await asyncio.sleep(random.randint(30, 90))
            await page.keyboard.press('Space')  # pause
            await asyncio.sleep(5)
            await page.goBack()
            await asyncio.sleep(3)
    
    # Solve captcha if triggered
    await solve_captcha(page)
    
    await browser.close()
    return True

async def run_cycle():
    with open(ACCOUNTS_FILE, 'r') as f:
        accounts = json.load(f)
    
    success_log = []
    for idx, acc in enumerate(accounts):
        proxy = PROXY_LIST[idx % len(PROXY_LIST)]
        try:
            result = await subscribe_account(acc, proxy)
            success_log.append({'email': acc['email'], 'status': 'success' if result else 'fail'})
            await asyncio.sleep(random.randint(DELAY_MIN, DELAY_MAX))
        except Exception as e:
            success_log.append({'email': acc['email'], 'status': 'error', 'msg': str(e)})
    
    # Write log
    with open('sub_log.csv', 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['email', 'status', 'msg'])
        for entry in success_log:
            writer.writerow(entry)

if __name__ == '__main__':
    asyncio.run(run_cycle())