# login_mt.py

from playwright.async_api import async_playwright
import asyncio
async def login():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto("https://mt.ua/auth/login")

        print("👉 Увійди вручну і натисни ENTER...")
        input()

        await context.storage_state(path="services/mt_auth.json")
        await browser.close()

  

if __name__ == "__main__":
    asyncio.run(login())